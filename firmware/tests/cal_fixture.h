/* Shared drive-calibration fixtures for the host tests. */
#ifndef CAL_FIXTURE_H
#define CAL_FIXTURE_H

#include "op/drive_cal.h"
#include <string.h>

#include "op/pump_controller.h"

#define TEST_UU OP_DRIVE_ZWBPD006006_UU_PER_STEP /* Rev A 5:1: 26100 uU = 0.0261 U per step */

static inline op_drive_cal_t test_cal(op_drive_id_t id)
{
    op_drive_cal_t c;
    (void)op_drive_cal_preset(id, &c);
    return c;
}

#define TEST_PAIR 0xA1B2C3D4u

/* pair + activate with a flat schedule (the pod must be filled and docked): Activate leaves it suspended */
static inline op_err_t test_activate(op_pump_t *p, uint32_t flat_rate_mu_h)
{
    op_err_t e = op_pump_set_pairing(p, TEST_PAIR, OP_ROLE_A);
    if (e != OP_OK) return e;
    op_activate_args_t a;
    memset(&a, 0, sizeof a);
    a.pair_id = TEST_PAIR;
    a.activation_id = 1;
    a.schedule.count = 1;
    a.schedule.seg[0].rate_mu_h = flat_rate_mu_h;
    return op_pump_activate(p, &a);
}

static inline const op_drive_cal_t *test_cal_5_1(void)
{
    static op_drive_cal_t c;
    c = test_cal(OP_DRIVE_ZWBPD006006_5_1);
    return &c;
}

#endif
