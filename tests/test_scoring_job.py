"""
Tests for modal_jobs/scoring_job.py.
No real Modal or NIM calls — all external I/O is mocked.
"""
from unittest.mock import MagicMock, patch

# Minimal two-chain PDB: one residue per chain, 4 Å apart — within the 8 Å threshold.
_SYNTHETIC_PDB = (
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 75.00           C  \n"
    "ATOM      2  CA  ALA B   1       0.000   4.000   0.000  1.00 75.00           C  \n"
    "END\n"
)


def _af2_result(pdb: str = _SYNTHETIC_PDB) -> dict:
    return {"pdbs": [pdb]}


class TestScoreSingle:
    def test_calls_af2_with_target_then_binder(self):
        """af2_multimer_predict receives sequences=[target, binder] in that order."""
        candidate = {
            "candidate_id": "c1",
            "binder_sequence": "ACDE",
            "target_sequence": "MNPQ",
        }
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(),
        ) as mock_af2:
            from modal_jobs.scoring_job import _score_single
            _score_single(candidate)

        mock_af2.assert_called_once_with(sequences=["MNPQ", "ACDE"])

    def test_result_has_required_keys(self):
        """Result dict contains candidate_id, pdockq, mean_interface_plddt, n_interface_contacts, pdb."""
        candidate = {"candidate_id": "c1", "binder_sequence": "ACDE", "target_sequence": "MNPQ"}
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(),
        ):
            from modal_jobs.scoring_job import _score_single
            result = _score_single(candidate)

        assert result["candidate_id"] == "c1"
        for key in ("pdockq", "mean_interface_plddt", "n_interface_contacts", "pdb"):
            assert key in result, f"Missing key: {key}"
        assert isinstance(result["pdockq"], float)

    def test_pdb_field_is_raw_string_from_af2_response(self):
        """result['pdb'] is the first PDB string from the AF2-Multimer response."""
        candidate = {"candidate_id": "c2", "binder_sequence": "A", "target_sequence": "M"}
        with patch(
            "modal_jobs.scoring_job.af2_multimer_predict",
            return_value=_af2_result(_SYNTHETIC_PDB),
        ):
            from modal_jobs.scoring_job import _score_single
            result = _score_single(candidate)

        assert result["pdb"] == _SYNTHETIC_PDB


class TestScoreCandidatesBatch:
    def test_map_called_once_with_full_list(self):
        """score_candidates_batch calls .map() once with the full candidates list, not per-item."""
        candidates = [
            {"candidate_id": "low",  "binder_sequence": "AA", "target_sequence": "MM"},
            {"candidate_id": "high", "binder_sequence": "CC", "target_sequence": "NN"},
        ]
        low  = {"candidate_id": "low",  "pdockq": 0.10, "mean_interface_plddt": 55.0,
                "n_interface_contacts": 2, "pdb": ""}
        high = {"candidate_id": "high", "pdockq": 0.45, "mean_interface_plddt": 82.0,
                "n_interface_contacts": 9, "pdb": ""}

        mock_map = MagicMock(return_value=iter([low, high]))
        with patch("modal_jobs.scoring_job.score_candidate") as mock_fn:
            mock_fn.map = mock_map
            from modal_jobs.scoring_job import score_candidates_batch
            results = score_candidates_batch(candidates)

        mock_map.assert_called_once_with(candidates)
        assert len(results) == 2

    def test_results_sorted_by_pdockq_descending(self):
        """Results come back highest pDockQ first regardless of input order."""
        candidates = [
            {"candidate_id": "low",  "binder_sequence": "AA", "target_sequence": "MM"},
            {"candidate_id": "high", "binder_sequence": "CC", "target_sequence": "NN"},
        ]
        low  = {"candidate_id": "low",  "pdockq": 0.10, "mean_interface_plddt": 55.0,
                "n_interface_contacts": 2, "pdb": ""}
        high = {"candidate_id": "high", "pdockq": 0.45, "mean_interface_plddt": 82.0,
                "n_interface_contacts": 9, "pdb": ""}

        mock_map = MagicMock(return_value=iter([low, high]))
        with patch("modal_jobs.scoring_job.score_candidate") as mock_fn:
            mock_fn.map = mock_map
            from modal_jobs.scoring_job import score_candidates_batch
            results = score_candidates_batch(candidates)

        assert results[0]["candidate_id"] == "high"
        assert results[1]["candidate_id"] == "low"
        assert results[0]["pdockq"] >= results[1]["pdockq"]
