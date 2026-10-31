import numpy as np
import pytest

from general_motion_retargeting.utils.smpl import fit_betas


def test_pads_smpl_betas_to_smplx_default():
    # GVHMR gives 10 SMPL betas; the default SMPL-X model expects 16.
    betas = np.arange(10, dtype=np.float32)
    out = fit_betas(betas, 16)
    assert out.shape == (16,)
    assert out.dtype == betas.dtype
    np.testing.assert_array_equal(out[:10], betas)
    np.testing.assert_array_equal(out[10:], 0)


def test_keeps_betas_when_sizes_match():
    # Model loaded with num_betas=10 (issue #164): nothing should be padded.
    betas = np.arange(10, dtype=np.float32)
    out = fit_betas(betas, 10)
    assert out.shape == (10,)
    np.testing.assert_array_equal(out, betas)


def test_truncates_betas_longer_than_model():
    betas = np.arange(16, dtype=np.float32)
    out = fit_betas(betas, 10)
    assert out.shape == (10,)
    np.testing.assert_array_equal(out, betas[:10])


@pytest.mark.parametrize("num_betas", [10, 16])
def test_resizes_last_axis_of_batched_betas(num_betas):
    betas = np.ones((2, 10), dtype=np.float32)
    out = fit_betas(betas, num_betas)
    assert out.shape == (2, num_betas)
    np.testing.assert_array_equal(out[:, :10], 1)
