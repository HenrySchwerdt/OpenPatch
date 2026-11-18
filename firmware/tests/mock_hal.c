#include <string.h>
#include "mock_hal.h"

static int m_step(void *c, uint32_t steps)
{
    mock_hal_t *m = c;
    if (!m->enabled) m->stepped_while_disabled = true;
    uint32_t n = steps;
    if (m->steps_limit >= 0 && (uint32_t)m->steps_limit < n) n = (uint32_t)m->steps_limit;
    m->total_steps += n;
    m->enc_x100 += (int64_t)n * 16 * m->delivered_pct;
    return (int)n;
}
static void m_enable(void *c, bool e)
{
    mock_hal_t *m = c;
    m->enabled = e;
    m->enable_calls++;
}
static int32_t m_enc(void *c) { return (int32_t)(((mock_hal_t *)c)->enc_x100 / 100); }
static void m_kick(void *c) { ((mock_hal_t *)c)->kicks++; }
static void m_buzz(void *c, op_buzzer_t p) { ((mock_hal_t *)c)->buzzer = p; }
static uint16_t m_batt(void *c) { return ((mock_hal_t *)c)->battery_mv; }
static uint64_t m_time(void *c) { return ((mock_hal_t *)c)->now_ms; }
static bool m_docked(void *c) { return ((mock_hal_t *)c)->docked; }
static bool m_charger(void *c) { return ((mock_hal_t *)c)->charger; }

void mock_hal_init(mock_hal_t *m)
{
    memset(m, 0, sizeof *m);
    m->battery_mv = 3900;
    m->delivered_pct = 100;
    m->steps_limit = -1;
    m->docked = true;
}

op_hal_t mock_hal_make(mock_hal_t *m)
{
    op_hal_t h = {m, m_step, m_enable, m_enc, m_kick, m_buzz, m_batt, m_time, m_docked, m_charger};
    return h;
}
