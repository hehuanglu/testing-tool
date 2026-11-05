source "${${(%):-%N}:A:h}/env.zsh"
cd "$WORKSPACE"
set -e
suite() {
  local label="$1"; shift
  "$ZAP_PYTHON" -B "$REPAIR_REVIEW/capture.py" "$label" "$ZAP_PYTHON" -B -m unittest "$@" -v
  tail -4 "$REPAIR_REVIEW/$label.stderr"
}
suite core-suite test_coordinator_recovery test_assessment_store test_operator_state test_operation_selection test_assessment_state_cli
suite regression-suite test_criteria_resume test_criteria_workflow test_criteria_cli_boundary test_criteria_native_read test_criteria_integration test_criteria_reporting_boundary test_evidence_allocation test_role_object_matrix test_resume_inputs test_work_session_checkpoint
suite safety-suite \
  test_runtime_safety.SafetyTests.test_atomic_short_write_never_exposes_final_name \
  test_runtime_safety.SafetyTests.test_truncated_journal_recovery_preserves_original \
  test_runtime_safety.SafetyTests.test_journal_middle_corruption_never_recovered_as_partial_tail \
  test_runtime_safety.SafetyTests.test_permanent_journal_fault_still_stops_and_records_out_of_band \
  test_runtime_safety.SafetyTests.test_reserved_channel_survives_writer_fault_and_rejects_torn_slot
suite repair-suite test_verification_repairs test_question_evidence test_work_selection
"$ZAP_PYTHON" -B "$REPAIR_REVIEW/capture.py" baseline-walkthrough "$ZAP_PYTHON" -B "$ASSESSMENT_ROOT/examples/state_recovery_walkthrough.py" "$REPAIR_REVIEW/baseline-walkthrough-fixture"
cat "$REPAIR_REVIEW/baseline-walkthrough.stdout"
