from __future__ import annotations

import unittest
from unittest.mock import patch

from buyer_agent.graph import execute_buyer_graph_with_trace


class BuyerGraphErrorPropagationTests(unittest.TestCase):
    def test_scope_rejection_is_returned_as_final_answer(self) -> None:
        rejection_reason = (
            "The query 'kl rahul' is ambiguous and does not clearly indicate a need for "
            "public web research, current information lookup, or comparison of options."
        )

        with (
            patch(
                "buyer_agent.graph.validate_scope",
                return_value={
                    "within_scope": False,
                    "scope_rejection_reason": rejection_reason,
                    "thinking": rejection_reason,
                },
            ),
            patch("buyer_agent.graph.decompose_goal") as decompose_goal,
            patch("buyer_agent.graph.synthesize_results") as synthesize_results,
        ):
            state, trace = execute_buyer_graph_with_trace(
                {
                    "user_goal": "kl rahul",
                    "task_id": "root-task",
                    "query": "kl rahul",
                    "thread_id": "test-thread",
                    "buyer_agent_id": "buyer",
                    "buyer_wallet_id": "buyer-wallet",
                    "buyer_wallet_address": "0x0000000000000000000000000000000000000002",
                    "buyer_agent_name": "Buyer",
                    "buyer_agent_description": "",
                    "buyer_agent_system_prompt": "",
                    "buyer_agent_connected_seller_ids": ["seller"],
                    "seller_agent_id": "seller",
                }
            )

        decompose_goal.assert_not_called()
        synthesize_results.assert_not_called()
        self.assertEqual(state["final_answer"], rejection_reason)
        self.assertEqual(state["result"]["summary"], rejection_reason)
        self.assertEqual(trace[-1].node_name, "validate_scope")
        self.assertEqual(trace[-1].status, "done")

    def test_payment_error_is_returned_instead_of_synthesized_answer(self) -> None:
        payment_error = "Payment processing failed: CircleWalletBadRequestException: insufficient balance"

        with (
            patch("buyer_agent.graph.validate_scope", return_value={"within_scope": True}),
            patch(
                "buyer_agent.graph.decompose_goal",
                return_value={
                    "tasks": [
                        {
                            "task_id": "task-1",
                            "query": "research arc testnet",
                            "objective": "Research Arc",
                        }
                    ]
                },
            ),
            patch(
                "buyer_agent.graph.discover_seller",
                return_value={
                    "seller_url": "http://seller.test/research",
                    "seller_wallet_id": "seller-wallet",
                    "seller_wallet_address": "0x0000000000000000000000000000000000000001",
                },
            ),
            patch("buyer_agent.graph.execute_payment", return_value={"error": payment_error}),
            patch("buyer_agent.graph.synthesize_results") as synthesize_results,
        ):
            state, trace = execute_buyer_graph_with_trace(
                {
                    "user_goal": "What is Arc?",
                    "task_id": "root-task",
                    "query": "What is Arc?",
                    "thread_id": "test-thread",
                    "buyer_agent_id": "buyer",
                    "buyer_wallet_id": "buyer-wallet",
                    "buyer_wallet_address": "0x0000000000000000000000000000000000000002",
                    "buyer_agent_name": "Buyer",
                    "buyer_agent_description": "",
                    "buyer_agent_system_prompt": "",
                    "buyer_agent_connected_seller_ids": ["seller"],
                    "seller_agent_id": "seller",
                }
            )

        synthesize_results.assert_not_called()
        self.assertEqual(state["error"], payment_error)
        self.assertNotIn("final_answer", state)
        self.assertEqual(state["task_errors"][0]["message"], payment_error)
        self.assertEqual(state["task_errors"][0]["task_id"], "task-1")
        self.assertEqual(trace[-1].node_name, "execute_payment_1")
        self.assertEqual(trace[-1].status, "error")
        self.assertEqual(trace[-1].output["error"], payment_error)


if __name__ == "__main__":
    unittest.main()
