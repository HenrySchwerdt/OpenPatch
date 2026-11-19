/*
 * VERIFY ON HARDWARE (written without a datasheet at hand and without a board):
 *  - TMAG5273 register map: DEVICE_CONFIG_2 (0x01) OPERATING_MODE, SENSOR_CONFIG_1 (0x02)
 *    MAG_CH_EN, SENSOR_CONFIG_2 (0x03) ANGLE_EN, ANGLE_RESULT (0x19/0x1A, 1/16 degree).
 *  - magnet orientation -> CONFIG_OPENPATCH_ENC_REVERSE.
 * The spindle makes one revolution per (steps/rev * gear ratio) motor steps, taken from the drive
 * calibration at boot (Rev A 5:1: 100 steps, 16:1: 320 steps): 5760 sensor counts (360 deg * 16)
 * correspond to steps_per_spindle_rev * 16 substeps.
 */
#include "encoder.h"

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/i2c.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "board_io.h"
#include "op/op_types.h"

LOG_MODULE_REGISTER(encoder, LOG_LEVEL_INF);

#define HAVE_TMAG (DT_NODE_HAS_STATUS(DT_NODELABEL(tmag5273), okay) && !IS_ENABLED(CONFIG_OPENPATCH_SIM_ENCODER))
#define HAVE_QDEC DT_NODE_HAS_STATUS(DT_ALIAS(qdec_hall), okay)

#define COUNTS_PER_REV 5760 /* 360 deg * 16 */

/* 0 until the calibration is known: the position then stays 0 (and delivery is blocked anyway) */
static uint32_t g_steps_per_spindle_rev;

void encoder_set_steps_per_spindle_rev(uint32_t steps)
{
    g_steps_per_spindle_rev = steps;
}

static int64_t g_sim_substeps;

#if HAVE_TMAG
static const struct i2c_dt_spec g_tmag = I2C_DT_SPEC_GET(DT_NODELABEL(tmag5273));
#define TMAG_REG_DEVICE_CONFIG_2 0x01
#define TMAG_REG_SENSOR_CONFIG_1 0x02
#define TMAG_REG_SENSOR_CONFIG_2 0x03
#define TMAG_REG_ANGLE 0x19
#define TMAG_MODE_STANDBY 0x00
#define TMAG_MODE_CONTINUOUS 0x02
static int64_t g_pos_counts;
static uint16_t g_last_angle;
static bool g_primed;
static bool g_tmag_ok = true; /* false: optional TMAG5273 did not answer, encoder is simulated */

static int tmag_sample(uint16_t *angle16)
{
    int rc = i2c_reg_write_byte_dt(&g_tmag, TMAG_REG_DEVICE_CONFIG_2, TMAG_MODE_CONTINUOUS);
    if (rc) return rc;
    k_msleep(3); /* one conversion */
    uint8_t b[2];
    rc = i2c_burst_read_dt(&g_tmag, TMAG_REG_ANGLE, b, 2);
    (void)i2c_reg_write_byte_dt(&g_tmag, TMAG_REG_DEVICE_CONFIG_2, TMAG_MODE_STANDBY); /* save power */
    if (rc) return rc;
    *angle16 = (uint16_t)((((uint16_t)b[0] << 8) | b[1]) & 0x1FFF);
    return 0;
}
#endif

int encoder_init(void)
{
#if HAVE_TMAG
    if (!i2c_is_ready_dt(&g_tmag)) return -ENODEV;
    int rc = i2c_reg_write_byte_dt(&g_tmag, TMAG_REG_SENSOR_CONFIG_1, 0x30); /* X + Y channels */
    if (!rc) rc = i2c_reg_write_byte_dt(&g_tmag, TMAG_REG_SENSOR_CONFIG_2, 0x04); /* angle from X-Y */
    if (rc) {
        if (IS_ENABLED(CONFIG_OPENPATCH_TMAG_OPTIONAL)) {
            /* Optional part (bench pod): without it there is no spindle slip measurement, so the
             * occlusion detector cannot see a blocked line; only the hall QDEC watchdog remains. */
            LOG_WRN("TMAG5273 not answering (%d): spindle encoder SIMULATED (open loop)", rc);
            g_tmag_ok = false;
            return 0;
        }
        LOG_ERR("TMAG5273 configuration failed (%d)", rc);
        return rc;
    }
#else
    LOG_WRN("spindle encoder SIMULATED (open loop)");
#endif
    return 0;
}

void encoder_sim_advance(uint32_t steps)
{
    g_sim_substeps += (int64_t)steps * OP_ENC_SUBSTEPS;
}

bool encoder_is_simulated(void)
{
#if HAVE_TMAG
    return !g_tmag_ok;
#else
    return true;
#endif
}

int32_t encoder_read_substeps(void)
{
#if HAVE_TMAG
    if (!g_tmag_ok) return (int32_t)g_sim_substeps;
    uint16_t a;
    if (tmag_sample(&a) != 0) {
        LOG_ERR("encoder read failed"); /* position freezes -> the supervisor sees a stall */
    } else {
        if (g_primed) {
            int32_t d = (int32_t)a - (int32_t)g_last_angle;
            if (d > COUNTS_PER_REV / 2) d -= COUNTS_PER_REV;
            if (d < -COUNTS_PER_REV / 2) d += COUNTS_PER_REV;
            g_pos_counts += IS_ENABLED(CONFIG_OPENPATCH_ENC_REVERSE) ? -d : d;
        }
        g_primed = true;
        g_last_angle = a;
    }
    return (int32_t)(g_pos_counts * (int64_t)(g_steps_per_spindle_rev * OP_ENC_SUBSTEPS) / COUNTS_PER_REV);
#else
    return (int32_t)g_sim_substeps;
#endif
}

bool encoder_qdec_counts(uint32_t *abs_counts)
{
#if HAVE_QDEC
    static const struct device *const qdec = DEVICE_DT_GET(DT_ALIAS(qdec_hall));
    static uint32_t total;
    struct sensor_value v;
    if (device_is_ready(qdec) && sensor_sample_fetch(qdec) == 0 &&
        sensor_channel_get(qdec, SENSOR_CHAN_ROTATION, &v) == 0) {
        /* degrees since the previous fetch; steps=4 in the devicetree => 90 deg per count */
        int32_t deg = v.val1 < 0 ? -v.val1 : v.val1;
        total += (uint32_t)(deg + 45) / 90u;
    }
    *abs_counts = total;
    return true;
#else
    ARG_UNUSED(abs_counts);
    return false;
#endif
}
