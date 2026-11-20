//! Step counting from the PHASE edges.
use openpatch_supervisor::phase::*;

const FWD: [(bool, bool); 4] = [(true, false), (true, true), (false, true), (false, false)];

#[test]
fn forward_sequence_counts_one_step_per_edge() {
    let mut d = PhaseDecoder::new(false, false);
    for (i, (a, b)) in FWD.iter().cycle().take(40).enumerate() {
        assert_eq!(d.sample(*a, *b), Decoded::Step(Dir::Forward), "edge {i}");
    }
}

#[test]
fn reverse_sequence_decodes_reverse() {
    let mut d = PhaseDecoder::new(false, false);
    let rev = [(false, true), (true, true), (true, false), (false, false)];
    for (a, b) in rev.iter().cycle().take(12) {
        assert_eq!(d.sample(*a, *b), Decoded::Step(Dir::Reverse));
    }
}

#[test]
fn direction_flip_is_decoded_from_the_order_of_the_transitions() {
    let mut d = PhaseDecoder::new(false, false);
    assert_eq!(d.sample(true, false), Decoded::Step(Dir::Forward));
    assert_eq!(d.sample(true, true), Decoded::Step(Dir::Forward));
    assert_eq!(d.sample(true, false), Decoded::Step(Dir::Reverse));
    assert_eq!(d.sample(false, false), Decoded::Step(Dir::Reverse));
}

#[test]
fn a_repeated_sample_changes_nothing() {
    let mut d = PhaseDecoder::new(true, true);
    assert_eq!(d.sample(true, true), Decoded::NoChange);
    assert_eq!(d.position(), 2);
}

#[test]
fn both_lines_at_once_is_a_sequence_error_and_resyncs() {
    let mut d = PhaseDecoder::new(false, false);
    assert_eq!(d.sample(true, true), Decoded::Invalid, "00 -> 11 skips a step");
    // after the error the decoder sits at the new levels: the next legal step counts again
    assert_eq!(d.sample(false, true), Decoded::Step(Dir::Forward));
    assert_eq!(d.sample(true, false), Decoded::Invalid, "01 -> 10");
}

#[test]
fn every_pair_of_states_is_classified_exactly() {
    let states = [(false, false), (true, false), (true, true), (false, true)];
    for (i, &(a0, b0)) in states.iter().enumerate() {
        for (j, &(a1, b1)) in states.iter().enumerate() {
            let mut d = PhaseDecoder::new(a0, b0);
            let want = match (j + 4 - i) % 4 {
                0 => Decoded::NoChange,
                1 => Decoded::Step(Dir::Forward),
                3 => Decoded::Step(Dir::Reverse),
                _ => Decoded::Invalid,
            };
            assert_eq!(d.sample(a1, b1), want, "{i} -> {j}");
        }
    }
}

#[test]
fn resync_does_not_count() {
    let mut d = PhaseDecoder::new(true, true);
    d.resync(false, false);
    assert_eq!(d.position(), 0);
    assert_eq!(d.sample(true, false), Decoded::Step(Dir::Forward));
}
