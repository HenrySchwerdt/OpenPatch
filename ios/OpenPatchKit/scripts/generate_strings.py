#!/usr/bin/env python3
"""Regenerates en/de Localizable.strings for OpenPatchKit and OpenPatchKitUI.

English text is the key. Fails if a key used in the Swift sources has no German translation.
Usage: python3 scripts/generate_strings.py
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

DE = {
 # ---- UI ----
 "Comms Issue": "Verbindungsproblem",
 "No Insulin": "Kein Insulin",
 "Pump Error": "Pumpenfehler",
 "Insulin Suspended": "Insulinabgabe pausiert",
 "No Pod": "Kein Pod",
 "Cancel": "Abbrechen",
 "Choose your pod size": "Pod-Größe wählen",
 "Continue": "Weiter",
 "The pod sizes only differ in reservoir length. Pick the size printed on your pod.": "Die Pod-Größen unterscheiden sich nur in der Reservoirlänge. Wähle die Größe, die auf deinem Pod steht.",
 "Pod size": "Pod-Größe",
 "Capacity: %.0f U of U100 insulin.": "Fassungsvermögen: %.0f IE U100-Insulin.",
 "OpenPatch is an experimental DIY device and not an approved medical device. Use it only if you understand the risks, and always keep a backup way to deliver insulin.": "OpenPatch ist ein experimentelles DIY-Gerät und kein zugelassenes Medizinprodukt. Nutze es nur, wenn du die Risiken verstehst, und halte immer eine Ersatzmöglichkeit zur Insulinabgabe bereit.",
 "Pair your pod": "Pod koppeln",
 "Place the pod next to your phone and wake it with the button. Nearby pods appear below.": "Lege den Pod neben dein Handy und wecke ihn mit dem Taster. Pods in der Nähe erscheinen unten.",
 "Bluetooth is off or not allowed for this app.": "Bluetooth ist aus oder für diese App nicht erlaubt.",
 "Searching for pods...": "Suche nach Pods ...",
 "Use simulated pod (development)": "Simulierten Pod verwenden (Entwicklung)",
 "Pairing...": "Kopplung läuft ...",
 "OpenPatch is delivering insulin": "OpenPatch gibt Insulin ab",
 "Done": "Fertig",
 "Basal delivery has started. Check your glucose regularly during the first hours.": "Die Basalabgabe läuft. Kontrolliere in den ersten Stunden regelmäßig deinen Glukosewert.",
 "Step %d: %@": "Schritt %d: %@",
 "Fill the pod with insulin": "Pod mit Insulin befüllen",
 "Pod is filled": "Pod ist befüllt",
 "Draw U100 insulin at room temperature into the syringe. Fill at least %.0f U.": "Ziehe U100-Insulin in Raumtemperatur in die Spritze auf. Mindestens %.0f IE.",
 "Tap the syringe and push out all air bubbles.": "Klopfe die Spritze ab und drücke alle Luftblasen heraus.",
 "Insert the needle straight into the fill port on the side of the pod.": "Steche die Nadel gerade in den Befüllanschluss an der Seite des Pods.",
 "Inject slowly until you have injected the amount below. Never exceed %.0f U.": "Spritze langsam, bis du die unten angegebene Menge injiziert hast. Niemals mehr als %.0f IE.",
 "Enter exactly how much insulin you injected, then confirm.": "Gib genau ein, wie viel Insulin du injiziert hast, und bestätige.",
 "Injected amount": "Injizierte Menge",
 "%.0f U": "%.0f IE",
 "Injected amount in units": "Injizierte Menge in Einheiten",
 "Priming uses about %.1f U.": "Das Entlüften verbraucht etwa %.1f IE.",
 "Prime the pod": "Pod entlüften",
 "Start priming": "Entlüften starten",
 "Hold the pod with the needle pointing up and away from you. Priming fills the needle with insulin and takes about %.0f seconds.": "Halte den Pod mit der Nadel nach oben und von dir weg. Beim Entlüften füllt sich die Nadel mit Insulin, das dauert etwa %.0f Sekunden.",
 "Priming...": "Entlüftung läuft ...",
 "Attach the pod": "Pod aufstecken",
 "Start insulin delivery": "Insulinabgabe starten",
 "Make sure the cannula (Accu-Chek Insight Flex) is inserted and the adhesive pad with the Velcro patch is in place.": "Stelle sicher, dass die Kanüle (Accu-Chek Insight Flex) gesetzt ist und das Pflaster mit dem Klettstück klebt.",
 "Align the pod with the cannula head and press it on until both side clips click.": "Richte den Pod am Kanülenkopf aus und drücke ihn auf, bis beide Seitenclips einrasten.",
 "Press the pod onto the Velcro patch and check that it sits firmly.": "Drücke den Pod auf das Klettstück und prüfe den festen Sitz.",
 "Tap the button below to start your basal program.": "Tippe unten auf die Schaltfläche, um dein Basalprogramm zu starten.",
 "If the pod does not click in place, do not start delivery.": "Wenn der Pod nicht einrastet, starte die Abgabe nicht.",
 "Delivery status is uncertain. Check the pod and your glucose.": "Der Abgabestatus ist unsicher. Prüfe den Pod und deinen Glukosewert.",
 "Remove OpenPatch from this app": "OpenPatch aus dieser App entfernen",
 "Remove OpenPatch?": "OpenPatch entfernen?",
 "Insulin delivery stops and the pod is deactivated.": "Die Insulinabgabe stoppt und der Pod wird deaktiviert.",
 "Remove": "Entfernen",
 "Pod": "Pod",
 "Status": "Status",
 "Size": "Größe",
 "Insulin": "Insulin",
 "Battery": "Akku",
 "Last sync": "Letzte Synchronisation",
 "Refresh": "Aktualisieren",
 "Insulin delivery": "Insulinabgabe",
 "Suspend insulin delivery": "Insulinabgabe pausieren",
 "Resume insulin delivery": "Insulinabgabe fortsetzen",
 "Not available in the current pod state.": "Im aktuellen Pod-Zustand nicht verfügbar.",
 "Pod handling": "Pod-Handhabung",
 "Refill and reuse pod": "Pod neu befüllen und weiterverwenden",
 "Remove pod from body": "Pod vom Körper abnehmen",
 "%.1f of %.0f U": "%.1f von %.0f IE",
 "Not paired": "Nicht gekoppelt",
 "Paired, empty": "Gekoppelt, leer",
 "Filled": "Befüllt",
 "Priming": "Entlüftung",
 "Ready to attach": "Bereit zum Aufstecken",
 "Delivering insulin": "Gibt Insulin ab",
 "Insulin delivery suspended": "Insulinabgabe pausiert",
 "Error": "Fehler",
 "Removed (can be refilled)": "Abgenommen (kann neu befüllt werden)",
 "Swap pod": "Pod wechseln",
 "Stopping the old pod": "Alter Pod wird gestoppt",
 "Dock the new pod": "Neuen Pod andocken",
 "Starting the new pod": "Neuer Pod wird gestartet",
 "Priming the cannula connector": "Kanülen-Anschluss wird befüllt",
 "Priming status unknown": "Befüllstatus unbekannt",
 "Starting insulin delivery": "Insulinabgabe wird gestartet",
 "The active pod is replaced by the spare pod. The spare is checked first; if it is not ready nothing changes.": "Der aktive Pod wird durch den Reserve-Pod ersetzt. Der Reserve-Pod wird zuerst geprüft; ist er nicht bereit, ändert sich nichts.",
 "Pod %@ is being told to stop. Stay close to it.": "Pod %@ wird gestoppt. Bleibe in seiner Nähe.",
 "Pod %@ did not confirm that it stopped. Try again, or - if you have taken it off the cannula - confirm that it is physically removed. The new pod does not start before one of the two.": "Pod %@ hat das Stoppen nicht bestätigt. Versuche es erneut oder bestätige, dass du ihn von der Kanüle genommen hast. Der neue Pod startet erst danach.",
 "Pod %@ has stopped. Take it off the cannula, put pod %@ on the cannula adapter and press Continue.": "Pod %@ ist gestoppt. Nimm ihn von der Kanüle ab, setze Pod %@ auf den Kanülenadapter und tippe auf Weiter.",
 "Pod %@ is being started with your basal program. If the connection drops, press Continue: the pod is never started twice.": "Pod %@ wird mit deinem Basalprogramm gestartet. Bricht die Verbindung ab, tippe auf Weiter: der Pod wird nie doppelt gestartet.",
 "Only the connector between pod %@ and the cannula is filled. The cannula itself is NOT primed.": "Nur der Anschluss zwischen Pod %@ und Kanüle wird befüllt. Die Kanüle selbst wird NICHT befüllt.",
 "The connection dropped while priming. Priming twice pushes a little more insulin into the connector. Choose: prime again, or continue without.": "Die Verbindung brach beim Befüllen ab. Zweimaliges Befüllen drückt etwas mehr Insulin in den Anschluss. Wähle: erneut befüllen oder ohne weiter.",
 "Pod %@ is primed. Press Continue to start insulin delivery.": "Pod %@ ist befüllt. Tippe auf Weiter, um die Insulinabgabe zu starten.",
 "Pods A / B": "Pods A / B",
 "This pod's drive calibration is missing or unknown. Delivery is blocked.": "Die Antriebskalibrierung dieses Pods fehlt oder ist unbekannt. Die Abgabe ist gesperrt.",
 "Pair spare pod": "Reserve-Pod koppeln",
 "Close": "Schließen",
 "Is the old pod removed?": "Ist der alte Pod entfernt?",
 "A pod that is off the cannula cannot deliver insulin. Only confirm if it is really removed from the cannula adapter.": "Ein Pod, der nicht auf der Kanüle sitzt, gibt kein Insulin ab. Bestätige nur, wenn er wirklich vom Kanülenadapter entfernt ist.",
 "Yes, it is removed": "Ja, er ist entfernt",
 "Start swap": "Wechsel starten",
 "Try again": "Erneut versuchen",
 "I removed the old pod from the cannula": "Ich habe den alten Pod von der Kanüle entfernt",
 "Cannot use the new pod: take the old pod back": "Neuer Pod nicht nutzbar: alten Pod wieder verwenden",
 "Prime again": "Erneut befüllen",
 "Continue without priming again": "Ohne erneutes Befüllen weiter",
 "Refresh spare pod": "Reserve-Pod aktualisieren",
 "Pod %@": "Pod %@",
 "Active": "Aktiv",
 "Spare": "Reserve",
 "Insulin: %@": "Insulin: %@",
 "Battery: %@": "Akku: %@",
 "Worn: %@": "Getragen: %@",
 "Dock: %@": "Dock: %@",
 "docked": "angedockt",
 "not docked": "nicht angedockt",
 "Pair the spare pod": "Reserve-Pod koppeln",
 "A second pod lets you swap without waiting: one pod delivers while the other is charged and refilled. Wake the spare pod with its button.": "Mit einem zweiten Pod wechselst du ohne Wartezeit: ein Pod gibt ab, der andere wird geladen und befüllt. Wecke den Reserve-Pod mit seinem Taster.",
 # ---- Kit ----
 "The pod does not report its drive calibration. It cannot be used: the insulin volume per step is unknown.": "Der Pod meldet seine Antriebskalibrierung nicht. Er kann nicht verwendet werden: das Insulinvolumen pro Schritt ist unbekannt.",
 "The pod reports an unknown drive (id %d, %d µU per step). It cannot be used.": "Der Pod meldet einen unbekannten Antrieb (ID %d, %d µE pro Schritt). Er kann nicht verwendet werden.",
 "A pod swap is in progress. Finish or cancel it first.": "Ein Pod-Wechsel läuft. Schließe ihn zuerst ab oder brich ihn ab.",
 "This pod is not the active pod.": "Dieser Pod ist nicht der aktive Pod.",
 "pod %@": "Pod %@",
 "Cannot reach %@. Move the phone closer and wake the pod with its button.": "%@ nicht erreichbar. Bringe das Handy näher und wecke den Pod mit dem Taster.",
 "The connection to %@ was lost while sending. The pod may or may not have executed the command.": "Die Verbindung zu %@ brach beim Senden ab. Der Pod hat den Befehl möglicherweise ausgeführt.",
 "%@ rejected the command (%@).": "%@ hat den Befehl abgelehnt (%@).",
 "%@ cannot be used: ": "%@ kann nicht verwendet werden: ",
 "%@ is not docked on the cannula yet.": "%@ sitzt noch nicht auf der Kanüle.",
 "The spare pod is not ready (charge it and fill it) - the swap was not started and the active pod keeps running.": "Der Reserve-Pod ist nicht bereit (laden und befüllen) - der Wechsel wurde nicht gestartet, der aktive Pod läuft weiter.",
 "Not possible right now (%@).": "Gerade nicht möglich (%@).",
 "Pod wear time": "Tragezeit des Pods",
 "Pod expired": "Pod abgelaufen",
 "Spare pod not ready": "Reserve-Pod nicht bereit",
 "Old pod not confirmed": "Alter Pod nicht bestätigt",
 "Two active pods": "Zwei aktive Pods",
 "Pod not docked": "Pod nicht angedockt",
 "Pod stopped": "Pod gestoppt",
 "Pod cannot be used": "Pod nicht verwendbar",
 "The pod lost its dock contact. It delivers no insulin until it sits on the cannula again.": "Der Pod hat den Dock-Kontakt verloren. Er gibt kein Insulin ab, bis er wieder auf der Kanüle sitzt.",
 "The pod has been worn for 44 hours. Swap to the other pod soon.": "Der Pod wird seit 44 Stunden getragen. Wechsle bald auf den anderen Pod.",
 "The pod reached its maximum wear time and stopped delivering insulin. Swap pods now.": "Der Pod hat die maximale Tragezeit erreicht und die Insulinabgabe gestoppt. Wechsle jetzt den Pod.",
 "The pod stopped delivering insulin (it was put on a charger or reached its wear limit). Swap pods.": "Der Pod hat die Insulinabgabe gestoppt (Ladegerät oder Tragezeit erreicht). Wechsle den Pod.",
 "The old pod did not confirm that it stopped. Confirm that it is physically removed or try again. The new pod will not start until then.": "Der alte Pod hat das Stoppen nicht bestätigt. Bestätige, dass er entfernt ist, oder versuche es erneut. Der neue Pod startet erst danach.",
 "Pod %@ reported that it was active although it must not be. It was told to stop.": "Pod %@ meldete sich aktiv, obwohl er es nicht sein darf. Er wurde gestoppt.",
 "Pod %@ has been worn for 44 hours or more. Swap to the other pod within %.0f hours.": "Pod %@ wird seit 44 Stunden oder länger getragen. Wechsle innerhalb von %.0f Stunden auf den anderen Pod.",
 "Pod %@ reached its maximum wear time and stopped delivering insulin. Swap pods now.": "Pod %@ hat die maximale Tragezeit erreicht und die Insulinabgabe gestoppt. Wechsle jetzt den Pod.",
 "Spare pod %@ is not ready: %@": "Reserve-Pod %@ ist nicht bereit: %@",
 "battery at %d %% - put it on the charger": "Akku bei %d %% - auf das Ladegerät legen",
 "only %.0f U inside, fill at least %.0f U": "nur %.0f IE enthalten, mindestens %.0f IE befüllen",
 "not seen recently - wake it with its button": "länger nicht gesehen - mit dem Taster wecken",
 "not checked yet": "noch nicht geprüft",
 "Pod is not ready (state: %@).": "Der Pod ist nicht bereit (Zustand: %@).",
 "A bolus is already in progress.": "Es läuft bereits ein Bolus.",
 "Insulin delivery is suspended.": "Die Insulinabgabe ist pausiert.",
 "No bolus is running.": "Es läuft kein Bolus.",
 "Invalid insulin amount.": "Ungültige Insulinmenge.",
 "Delivery limit exceeded (%@).": "Abgabegrenze überschritten (%@).",
 "The pod rejected the command (%@).": "Der Pod hat den Befehl abgelehnt (%@).",
 "Communication with the pod failed (%@).": "Kommunikation mit dem Pod fehlgeschlagen (%@).",
 "The basal schedule has not been set yet.": "Das Basalprofil wurde noch nicht festgelegt.",
 "Invalid fill amount (%@).": "Ungültige Füllmenge (%@).",
 "The pod reported a fault (%@).": "Der Pod meldet einen Fehler (%@).",
 "Low insulin": "Wenig Insulin",
 "OpenPatch error": "OpenPatch-Fehler",
 "Pod battery low": "Pod-Akku schwach",
 "Connection lost": "Verbindung verloren",
 "The pod ended the temporary basal rate after losing contact with the phone.": "Der Pod hat die temporäre Basalrate beendet, nachdem die Verbindung zum Handy abgebrochen war.",
 "About %.0f U of insulin left.": "Noch etwa %.0f IE Insulin.",
 "The pod stopped insulin delivery (%@). Replace or refill the pod.": "Der Pod hat die Insulinabgabe gestoppt (%@). Pod wechseln oder neu befüllen.",
 "Pod battery at %d %%. Charge the pod soon.": "Pod-Akku bei %d %%. Lade den Pod bald auf.",
 "OK": "OK",
 "Delivery status uncertain": "Abgabestatus unsicher",
 "Check pod again": "Pod erneut prüfen",
 "%@ lost contact with the pod while changing insulin delivery (%@). The pod may or may not have executed the command.": "%@ hat beim Ändern der Insulinabgabe die Verbindung zum Pod verloren (%@). Der Pod hat den Befehl möglicherweise ausgeführt, möglicherweise nicht.",
 "Move your phone close to the pod and check again. If you cannot reach the pod, check your glucose and treat as needed.": "Halte dein Handy nah an den Pod und prüfe erneut. Wenn du den Pod nicht erreichst, kontrolliere deinen Glukosewert und handle nach Bedarf.",
 "I checked the pod and my glucose - continue": "Ich habe Pod und Glukosewert geprüft - weiter",
}

def keys_in(folder, pattern):
    out = []
    for f in sorted((ROOT / folder).rglob("*.swift")):
        text = f.read_text()
        for m in re.finditer(pattern, text):
            out.append(bytes(m.group(1), "utf-8").decode("unicode_escape") if "\\" in m.group(1) else m.group(1))
    return out

ui_keys = keys_in("OpenPatchKitUI", r'\bL\(\s*"((?:[^"\\]|\\.)*)"')
kit_keys = keys_in("OpenPatchKit", r'NSLocalizedString\(\s*"((?:[^"\\]|\\.)*)"')

def esc(s): return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def write(folder, keys):
    uniq = list(dict.fromkeys(keys))
    missing = [k for k in uniq if k not in DE]
    if missing:
        print("MISSING German translation:", *missing, sep="\n  ")
        sys.exit(1)
    for lang in ("en", "de"):
        d = ROOT / folder / "Resources" / f"{lang}.lproj"
        d.mkdir(parents=True, exist_ok=True)
        lines = ['/* Generated by scripts/generate_strings.py - edit DE table there. */']
        for k in uniq:
            lines.append(f'"{esc(k)}" = "{esc(k if lang == "en" else DE[k])}";')
        (d / "Localizable.strings").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{folder}: {len(uniq)} keys x en/de")

write("OpenPatchKitUI", ui_keys)
write("OpenPatchKit", kit_keys)
