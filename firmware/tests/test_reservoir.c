#include "op/reservoir_model.h"
#include "cal_fixture.h"
#include "op_test.h"

TEST(res_unfilled_is_neither_empty_nor_low)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_200_MU, TEST_UU);
    CHECK_EQ(op_res_remaining_mu(&r), 0);
    CHECK(!op_res_is_empty(&r));
    CHECK(!op_res_is_low(&r));
}

TEST(res_fill_validation)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_100_MU, TEST_UU);
    CHECK_EQ(op_res_fill(&r, 0), OP_ERR_BAD_ARG);
    CHECK_EQ(op_res_fill(&r, OP_CAPACITY_100_MU + 1), OP_ERR_LIMIT);
    CHECK_EQ(op_res_fill(&r, OP_CAPACITY_100_MU), OP_OK);
    CHECK_EQ(op_res_remaining_mu(&r), 100000);
}

TEST(res_consume_reduces_remaining_exactly)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_200_MU, TEST_UU);
    op_res_fill(&r, 100000);
    op_res_consume(&r, 1000); /* 26.1 U */
    CHECK_EQ(op_res_remaining_mu(&r), 73900);
    op_res_consume(&r, 1); /* 100000 - 26126.1 mU -> floor */
    CHECK_EQ(op_res_remaining_mu(&r), 73873);
}

TEST(res_low_alarm_threshold)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_100_MU, TEST_UU);
    op_res_fill(&r, 20000);
    CHECK(!op_res_is_low(&r));
    op_res_consume(&r, 383); /* 9996.3 mU -> remaining 10003 -> not yet */
    CHECK(!op_res_is_low(&r));
    op_res_consume(&r, 1); /* 10022.4 mU -> remaining 9977 */
    CHECK(op_res_is_low(&r));
    CHECK(!op_res_is_empty(&r));
    CHECK_EQ(op_res_set_low_threshold(&r, 5000), OP_OK);
    CHECK(!op_res_is_low(&r));
    CHECK_EQ(op_res_set_low_threshold(&r, OP_CAPACITY_100_MU + 1), OP_ERR_BAD_ARG);
}

TEST(res_empty_and_saturating_consume)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_70_MU, TEST_UU);
    op_res_fill(&r, 1000);
    op_res_consume(&r, 100000);
    CHECK_EQ(op_res_remaining_mu(&r), 0);
    CHECK(op_res_is_empty(&r));
    CHECK(op_res_is_low(&r));
}

TEST(res_refill_resets_consumption)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_70_MU, TEST_UU);
    op_res_fill(&r, 5000);
    op_res_consume(&r, 100);
    op_res_fill(&r, 60000);
    CHECK_EQ(op_res_remaining_mu(&r), 60000);
    CHECK_EQ(r.consumed_steps, 0);
}

TEST(res_default_low_threshold_is_10_units)
{
    op_res_t r;
    op_res_init(&r, OP_CAPACITY_70_MU, TEST_UU);
    CHECK_EQ(r.low_threshold_mu, 10000);
}
