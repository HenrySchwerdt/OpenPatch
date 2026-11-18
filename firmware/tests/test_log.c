#include "op/event_log.h"
#include "op_test.h"

TEST(log_ids_start_at_one_and_increase)
{
    op_log_t l;
    op_log_init(&l);
    CHECK_EQ(op_log_oldest_id(&l), op_log_next_id(&l));
    CHECK_EQ(op_log_append(&l, 10, OP_EV_BOOT, 0, 0), 1);
    CHECK_EQ(op_log_append(&l, 11, OP_EV_RESUME, 7, 8), 2);
    op_event_t e[4];
    CHECK_EQ(op_log_read(&l, 1, e, 4), 2);
    CHECK_EQ(e[1].id, 2);
    CHECK_EQ(e[1].time_s, 11);
    CHECK_EQ(e[1].type, OP_EV_RESUME);
    CHECK_EQ(e[1].a, 7);
    CHECK_EQ(e[1].b, 8);
}

TEST(log_read_from_id_and_max)
{
    op_log_t l;
    op_log_init(&l);
    for (int i = 0; i < 10; i++) op_log_append(&l, 0, OP_EV_BOOT, i, 0);
    op_event_t e[4];
    CHECK_EQ(op_log_read(&l, 5, e, 4), 4);
    CHECK_EQ(e[0].id, 5);
    CHECK_EQ(e[3].id, 8);
    CHECK_EQ(op_log_read(&l, 11, e, 4), 0);
    CHECK_EQ(op_log_read(&l, 5, e, 0), 0);
    CHECK_EQ(op_log_read(&l, 5, NULL, 4), 0);
}

TEST(log_ring_overwrites_oldest_but_ids_persist)
{
    op_log_t l;
    op_log_init(&l);
    for (uint32_t i = 0; i < OP_LOG_CAPACITY + 72; i++) op_log_append(&l, 0, OP_EV_BOOT, (int32_t)i, 0);
    CHECK_EQ(l.count, OP_LOG_CAPACITY);
    CHECK_EQ(op_log_next_id(&l), OP_LOG_CAPACITY + 72 + 1);
    CHECK_EQ(op_log_oldest_id(&l), 73);
    op_event_t e[OP_LOG_CAPACITY];
    CHECK_EQ(op_log_read(&l, 1, e, OP_LOG_CAPACITY), OP_LOG_CAPACITY);
    CHECK_EQ(e[0].id, 73);
    CHECK_EQ(e[0].a, 72);
    CHECK_EQ(e[OP_LOG_CAPACITY - 1].id, OP_LOG_CAPACITY + 72);
}

TEST(log_restore_continues_persistent_ids)
{
    op_log_t l;
    op_log_init(&l);
    op_log_restore(&l, 1000);
    CHECK_EQ(op_log_oldest_id(&l), 1000);
    CHECK_EQ(op_log_append(&l, 0, OP_EV_BOOT, 0, 0), 1000);
    op_log_restore(&l, 0); /* 0 is invalid -> clamps to 1 */
    CHECK_EQ(op_log_next_id(&l), 1);
}
