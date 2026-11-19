//! Deterministic PRNG (xoshiro256++ seeded by splitmix64). No external dependency, no OS entropy:
//! the same seed always reproduces the same run, bit for bit.

#[derive(Clone, Debug)]
pub struct Rng {
    s: [u64; 4],
    spare: Option<f64>,
}

fn splitmix(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        let mut st = seed;
        let s = [splitmix(&mut st), splitmix(&mut st), splitmix(&mut st), splitmix(&mut st)];
        Rng { s, spare: None }
    }

    /// Independent stream derived from this seed (e.g. one per Monte Carlo run / per subsystem).
    pub fn fork(seed: u64, stream: u64) -> Self {
        Rng::new(seed ^ stream.wrapping_mul(0xD6E8_FEB8_6659_FD93).rotate_left(17))
    }

    pub fn next_u64(&mut self) -> u64 {
        let r = (self.s[0].wrapping_add(self.s[3])).rotate_left(23).wrapping_add(self.s[0]);
        let t = self.s[1] << 17;
        self.s[2] ^= self.s[0];
        self.s[3] ^= self.s[1];
        self.s[1] ^= self.s[2];
        self.s[0] ^= self.s[3];
        self.s[2] ^= t;
        self.s[3] = self.s[3].rotate_left(45);
        r
    }

    /// Uniform in [0, 1).
    pub fn uniform(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    pub fn range(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.uniform()
    }

    /// Standard normal (Box-Muller, cached spare).
    pub fn gauss(&mut self) -> f64 {
        if let Some(s) = self.spare.take() {
            return s;
        }
        let mut u1 = self.uniform();
        if u1 < 1e-300 {
            u1 = 1e-300;
        }
        let u2 = self.uniform();
        let r = (-2.0 * u1.ln()).sqrt();
        let th = 2.0 * std::f64::consts::PI * u2;
        self.spare = Some(r * th.sin());
        r * th.cos()
    }

    /// Normal truncated to +-`k` sigma (rejection), for manufacturing tolerances.
    pub fn gauss_trunc(&mut self, k: f64) -> f64 {
        loop {
            let g = self.gauss();
            if g.abs() <= k {
                return g;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_stream() {
        let mut a = Rng::new(42);
        let mut b = Rng::new(42);
        for _ in 0..100 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
        let mut c = Rng::new(43);
        assert_ne!(Rng::new(42).next_u64(), c.next_u64());
    }

    #[test]
    fn gauss_moments() {
        let mut r = Rng::new(7);
        let n = 200_000;
        let (mut s, mut s2) = (0.0, 0.0);
        for _ in 0..n {
            let g = r.gauss();
            s += g;
            s2 += g * g;
        }
        let m = s / n as f64;
        let v = s2 / n as f64 - m * m;
        assert!(m.abs() < 0.01, "mean {m}");
        assert!((v - 1.0).abs() < 0.02, "var {v}");
    }
}
