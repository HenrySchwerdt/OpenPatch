//! JSON-lines interface to a live virtual pod, for end-to-end harnesses (the iOS app's
//! `SimulatedPod`, the diagnostics system, scripts). One JSON object per line in, one per line out.
//! Over stdio (`opsim serve --stdio`) or TCP (`opsim serve --tcp 127.0.0.1:7878`, one client at a
//! time). The simulation only advances when told to (`run`): fully deterministic and as fast as the
//! host allows.
//!
//! Requests (`"cmd"`):
//!
//! * `new`: `{"cmd":"new","builtin":"wear_48h"}` or `{"cmd":"new","scenario":{...}}`; optional
//!   `"standard_setup":false` skips the draw / dock / activate / prime / resume sequence.
//! * `run`: `{"cmd":"run","seconds":60}`
//! * `inject`: `{"cmd":"inject","action":{"action":"bolus","units":1.0}}` (any scenario `Action`: phone
//!   commands and physical / electrical faults)
//! * `frame`: `{"cmd":"frame","hex":"01..."}`, a protocol v1 frame (plaintext) straight into
//!   `Pump::handle_frame`; the answer frame comes back as hex
//! * `status`: snapshot only
//! * `verdict`: the running verdict (same JSON as `opsim run`)
//! * `quit`
//!
//! Every reply has `"ok"` and, after `new` / `run` / `inject` / `status`, a `"state"` snapshot with
//! what the app would see (decoded `GetStatus`) and the physical truth (`"plant"`).

use crate::runner::{fault_names, Runner, MU_PER_UL};
use crate::scenario::{Action, Scenario};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};

pub struct Server {
    runner: Option<Runner>,
    last_fault_bits: u16,
}

impl Default for Server {
    fn default() -> Self {
        Server::new()
    }
}

fn hex_decode(s: &str) -> Result<Vec<u8>, String> {
    let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    if s.len() % 2 != 0 {
        return Err("odd hex length".into());
    }
    (0..s.len()).step_by(2).map(|i| u8::from_str_radix(&s[i..i + 2], 16).map_err(|_| "bad hex".to_string())).collect()
}

fn hex_encode(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

impl Server {
    pub fn new() -> Self {
        Server { runner: None, last_fault_bits: 0 }
    }

    fn err(msg: impl Into<String>) -> Value {
        json!({"ok": false, "error": msg.into()})
    }

    fn snapshot(&mut self) -> Value {
        let r = self.runner.as_mut().expect("runner");
        let t_s = r.now_s();
        let status = r.dev.status();
        let (plant, power_on, resets) = {
            let w = r.dev.world.borrow();
            (
                json!({
                    "needle_out_mu": w.plant.out_ul * MU_PER_UL,
                    "reservoir_actual_mu": w.plant.liquid_ul * MU_PER_UL,
                    "pressure_kpa": w.plant.pressure_kpa,
                    "plunger_mm": w.plant.plunger_x,
                    "lost_steps": w.plant.lost_steps,
                    "docked": w.docked_phys,
                    "battery_mv": w.battery_idle_mv(),
                    "buzzer": format!("{:?}", w.buzzer),
                    "line_air_ul": w.plant.line_air_ul,
                }),
                w.power_on,
                w.stats.resets.len(),
            )
        };
        let state = match status {
            Some(s) => {
                let faults = fault_names(s.faults);
                let new = s.faults & !self.last_fault_bits;
                self.last_fault_bits = s.faults;
                json!({
                    "flags": s.flags,
                    "faults": s.faults,
                    "fault_names": faults,
                    "new_fault_names": fault_names(new),
                    "reservoir_mu": s.reservoir_mu,
                    "delivered_mu": s.delivered_mu,
                    "scheduled_mu": s.scheduled_mu,
                    "battery_mv": s.battery_mv,
                    "current_rate_mu_h": s.current_rate_mu_h,
                    "bolus_remaining_mu": s.bolus_remaining_mu,
                    "temp_rate_mu_h": s.temp_rate_mu_h,
                    "temp_remaining_min": s.temp_remaining_min,
                    "delivery_state": s.delivery_state,
                    "wear_s": s.wear_s,
                    "draw_state": s.draw_state,
                    "draw_done_mu": s.draw_done_mu,
                    "next_event_id": s.next_event_id,
                })
            }
            None => Value::Null, // pod off / hung / booting: no answer, like a lost BLE link
        };
        json!({"t_s": t_s, "power_on": power_on, "resets": resets, "pod": state, "plant": plant})
    }

    pub fn handle(&mut self, line: &str) -> Value {
        let req: Value = match serde_json::from_str(line) {
            Ok(v) => v,
            Err(e) => return Self::err(format!("bad json: {e}")),
        };
        let Some(cmd) = req.get("cmd").and_then(|c| c.as_str()) else {
            return Self::err("missing cmd");
        };
        match cmd {
            "new" => {
                let sc: Result<Scenario, String> = if let Some(b) = req.get("builtin").and_then(|v| v.as_str()) {
                    crate::scenarios::get(b)
                } else if let Some(s) = req.get("scenario") {
                    serde_json::from_value(s.clone()).map_err(|e| e.to_string())
                } else {
                    Ok(Scenario::default())
                };
                let mut sc = match sc {
                    Ok(s) => s,
                    Err(e) => return Self::err(e),
                };
                if let Some(false) = req.get("standard_setup").and_then(|v| v.as_bool()) {
                    sc.setup.standard = false;
                }
                let mut r = match Runner::new(sc) {
                    Ok(r) => r,
                    Err(e) => return Self::err(e),
                };
                r.run_setup();
                let v = r.verdict();
                self.runner = Some(r);
                self.last_fault_bits = 0;
                let mut snap = self.snapshot();
                snap["setup_ok"] = json!(v.setup_ok);
                snap["setup_note"] = json!(v.setup_note);
                json!({"ok": true, "state": snap})
            }
            _ if self.runner.is_none() => Self::err("no pod: send {\"cmd\":\"new\"} first"),
            "run" => {
                let s = req.get("seconds").and_then(|v| v.as_f64()).unwrap_or(1.0);
                if !(0.0..=1.0e7).contains(&s) {
                    return Self::err("seconds out of range");
                }
                let r = self.runner.as_mut().unwrap();
                let t = r.now_s() + s;
                r.advance_to_s(t);
                json!({"ok": true, "state": self.snapshot()})
            }
            "inject" => {
                let a: Result<Action, _> = serde_json::from_value(req.get("action").cloned().unwrap_or(Value::Null));
                match a {
                    Ok(a) => {
                        self.runner.as_mut().unwrap().exec(&a);
                        json!({"ok": true, "state": self.snapshot()})
                    }
                    Err(e) => Self::err(format!("bad action: {e}")),
                }
            }
            "frame" => {
                let Some(h) = req.get("hex").and_then(|v| v.as_str()) else { return Self::err("hex missing") };
                let bytes = match hex_decode(h) {
                    Ok(b) => b,
                    Err(e) => return Self::err(e),
                };
                let out = self.runner.as_mut().unwrap().dev.handle_raw_frame(&bytes);
                json!({"ok": true, "response_hex": out.map(|o| hex_encode(&o))})
            }
            "status" => json!({"ok": true, "state": self.snapshot()}),
            "verdict" => {
                let v = self.runner.as_ref().unwrap().verdict();
                json!({"ok": true, "verdict": serde_json::to_value(&v).unwrap()})
            }
            other => Self::err(format!("unknown cmd {other:?}")),
        }
    }
}

fn serve_stream<R: BufRead, W: Write>(srv: &mut Server, input: R, mut out: W) -> std::io::Result<()> {
    for line in input.lines() {
        let line = line?;
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if line.contains("\"quit\"") && serde_json::from_str::<Value>(line).ok().and_then(|v| v.get("cmd").cloned()) == Some(json!("quit")) {
            writeln!(out, "{}", json!({"ok": true, "bye": true}))?;
            out.flush()?;
            break;
        }
        let reply = srv.handle(line);
        writeln!(out, "{reply}")?;
        out.flush()?;
    }
    Ok(())
}

pub fn cli(args: &[String]) -> Result<bool, String> {
    let mut srv = Server::new();
    if let Some(i) = args.iter().position(|a| a == "--tcp") {
        let addr = args.get(i + 1).ok_or("--tcp needs ADDR")?;
        let l = std::net::TcpListener::bind(addr).map_err(|e| format!("{addr}: {e}"))?;
        eprintln!("opsim: listening on {addr} (JSON lines, one client at a time)");
        for conn in l.incoming() {
            let conn = conn.map_err(|e| e.to_string())?;
            let reader = BufReader::new(conn.try_clone().map_err(|e| e.to_string())?);
            serve_stream(&mut srv, reader, conn).map_err(|e| e.to_string())?;
        }
        Ok(true)
    } else {
        let stdin = std::io::stdin();
        serve_stream(&mut srv, stdin.lock(), std::io::stdout()).map_err(|e| e.to_string())?;
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_run_inject_status_roundtrip() {
        let mut s = Server::new();
        let r = s.handle(r#"{"cmd":"new","scenario":{"setup":{"fill_u":20.0}}}"#);
        assert_eq!(r["ok"], true, "{r}");
        assert_eq!(r["state"]["setup_ok"], true, "{r}");
        let r = s.handle(r#"{"cmd":"inject","action":{"action":"bolus","units":1.0}}"#);
        assert_eq!(r["ok"], true);
        let r = s.handle(r#"{"cmd":"run","seconds":120}"#);
        assert_eq!(r["state"]["pod"]["bolus_remaining_mu"], 0, "{r}");
        let out = r["state"]["plant"]["needle_out_mu"].as_f64().unwrap();
        assert!(out > 400.0 && out < 1100.0, "needle out {out}"); // the first bolus after a draw loses the lost motion
        let r = s.handle(r#"{"cmd":"status"}"#);
        assert!(r["state"]["pod"]["delivered_mu"].as_u64().unwrap() >= 1000);
    }

    #[test]
    fn raw_frames_reach_the_pump() {
        use openpatch_proto::{self as proto, Command, CommandBody, NoCrypto, Session};
        let mut s = Server::new();
        s.handle(r#"{"cmd":"new","scenario":{"setup":{"fill_u":20.0}}}"#);
        let mut payload = [0u8; 64];
        let cmd = Command::new(500, CommandBody::GetStatus);
        let n = proto::encode_command_payload(&cmd, &mut payload).unwrap();
        let mut sess = Session::new(NoCrypto, false, [0; 4], true);
        let mut frame = [0u8; 128];
        let l = sess.seal(false, cmd.body.type_id(), 500, false, &payload[..n], &mut frame).unwrap();
        let r = s.handle(&format!(r#"{{"cmd":"frame","hex":"{}"}}"#, hex_encode(&frame[..l])));
        let hex = r["response_hex"].as_str().expect("response").to_string();
        let bytes = hex_decode(&hex).unwrap();
        let f = proto::decode_frame(&bytes).unwrap();
        let rsp = proto::decode_response(f.type_ & !proto::RSP_BIT, f.seq, f.payload).unwrap();
        assert_eq!(rsp.result, 0);
        assert!(rsp.status.unwrap().flags & proto::st::ACTIVE != 0);
    }

    #[test]
    fn errors_are_replies_not_panics() {
        let mut s = Server::new();
        assert_eq!(s.handle("not json")["ok"], false);
        assert_eq!(s.handle(r#"{"cmd":"run","seconds":1}"#)["ok"], false);
        s.handle(r#"{"cmd":"new"}"#);
        assert_eq!(s.handle(r#"{"cmd":"inject","action":{"action":"nope"}}"#)["ok"], false);
        assert_eq!(s.handle(r#"{"cmd":"frame","hex":"zz"}"#)["ok"], false);
    }

    #[test]
    fn stream_loop_answers_every_line() {
        let mut s = Server::new();
        let input = "{\"cmd\":\"new\"}\n\n{\"cmd\":\"run\",\"seconds\":5}\n{\"cmd\":\"quit\"}\n{\"cmd\":\"run\",\"seconds\":5}\n";
        let mut out = Vec::new();
        serve_stream(&mut s, input.as_bytes(), &mut out).unwrap();
        let lines: Vec<&str> = std::str::from_utf8(&out).unwrap().lines().collect();
        assert_eq!(lines.len(), 3);
        assert!(lines[2].contains("bye"));
    }
}
