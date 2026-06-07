import warnings

import numpy as np
from quimb.tensor import tensor_network_1d_compress, MatrixProductOperator, MatrixProductState, Circuit

from qiskit_quimb import quimb_circuit
from qiskit import QuantumCircuit

# ------------------------------------------------------------------
#  Constructors
# ------------------------------------------------------------------

def mpo_from_circuit(circ: Circuit):
    # add dummy rz to cover all sites
    for q in range(circ.N):
    #    circ.rz(0.0, q)
        circ.u3(0, 0, 0, q)
    tn_uni = circ.get_uni()

    # contract gates per site tag
    for st in list(tn_uni.site_tags):
        tn_uni ^= st

    # make sure bonds are simple 1D chain bonds
    tn_uni.fuse_multibonds_()  

    # cast as MatrixProductOperator
    mpo = tn_uni.view_as_(
        MatrixProductOperator,
        cyclic=False,
        L=circ.N,
    )

    mpo.ensure_bonds_exist()
    return mpo


# ------------------------------------------------------------------
#  MPO x MPO composition
# ------------------------------------------------------------------

def _is_svd_convergence_error(exc):
    msg = str(exc).lower()
    return (
        "svd" in msg
        and (
            "converge" in msg
            or "ill-conditioned" in msg
            or "linalg" in msg
        )
    )


def _is_torch_oom_error(exc):
    try:
        import torch
        if isinstance(exc, torch.OutOfMemoryError):
            return True
    except Exception:
        pass
    msg = str(exc).lower()
    return "out of memory" in msg and ("cuda" in msg or "hip" in msg or "torch" in msg)


def _is_mixed_backend_error(exc):
    msg = str(exc).lower()
    return (
        "tensordot" in msg
        and (
            "must be tensor, not numpy.ndarray" in msg
            or "must be ndarray, not tensor" in msg
            or "must be numpy.ndarray, not tensor" in msg
        )
    )


def _clear_torch_cache():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _torch_context(*tns):
    try:
        import torch
    except Exception:
        return None

    for tn in tns:
        for tensor in tn:
            data = tensor.data
            if isinstance(data, torch.Tensor):
                return data.device, data.dtype
    return None


def _network_to_numpy(tn):
    out = tn.copy()
    try:
        import torch
    except Exception:
        torch = None

    def convert(x):
        if torch is not None and isinstance(x, torch.Tensor):
            y = x.detach()
            _clear_torch_cache()
            is_conj = bool(y.is_conj()) if hasattr(y, "is_conj") else False
            is_neg = bool(y.is_neg()) if hasattr(y, "is_neg") else False
            base = getattr(y, "_base", None)
            if base is not None:
                base_cpu = base.detach().cpu()
                y = base_cpu.as_strided(tuple(y.shape), tuple(y.stride()), y.storage_offset())
                if is_conj:
                    y = y.conj()
                if is_neg:
                    y = -y
            else:
                y = y.cpu()
            if hasattr(y, "resolve_conj"):
                y = y.resolve_conj()
            if hasattr(y, "resolve_neg"):
                y = y.resolve_neg()
            return y.contiguous().numpy()
        return np.asarray(x)

    out.apply_to_arrays(convert)
    return out


def _network_to_torch(tn, device, dtype):
    import torch

    out = tn.copy()
    out.apply_to_arrays(lambda x: torch.as_tensor(x, device=device, dtype=dtype))
    return out


def stable_apply_operator(operator, target, *, compress=False, contract=True, **compress_opts):
    """
    Apply one tensor-network operator to another network with robust compression.

    CUDA SVD can fail to converge on ill-conditioned reduced compression cores.
    Preserve the requested max_bond/cutoff, but retry with an alternate Quimb
    split method and finally perform just this compression on CPU if needed.
    """
    first_error = None
    second_error = None
    try:
        return operator.apply(
            target,
            compress=compress,
            contract=contract,
            **compress_opts,
        )
    except Exception as exc:
        if not (
            _is_mixed_backend_error(exc)
            or (compress and (_is_svd_convergence_error(exc) or _is_torch_oom_error(exc)))
        ):
            raise
        _clear_torch_cache()
        first_error = exc

    if _is_svd_convergence_error(first_error):
        retry_opts = dict(compress_opts)
        retry_opts.setdefault("method", "svd:eig")
        try:
            warnings.warn(
                "Tensor-network compression hit a CUDA SVD convergence failure; "
                "retrying with Quimb method='svd:eig'.",
                RuntimeWarning,
                stacklevel=2,
            )
            return operator.apply(
                target,
                compress=compress,
                contract=contract,
                **retry_opts,
            )
        except Exception as exc:
            if not (_is_svd_convergence_error(exc) or _is_torch_oom_error(exc)):
                raise
            _clear_torch_cache()
            second_error = exc

    context = _torch_context(operator, target)
    if context is None:
        raise (second_error or first_error)

    device, dtype = context
    if _is_mixed_backend_error(first_error):
        reason = "mixed torch/numpy backend"
    elif _is_svd_convergence_error(first_error):
        reason = "SVD convergence"
    else:
        reason = "GPU memory"
    warnings.warn(
        f"Tensor-network compression hit a {reason} failure; retrying this "
        "operator application on CPU and moving the compressed result back.",
        RuntimeWarning,
        stacklevel=2,
    )
    operator_cpu = _network_to_numpy(operator)
    target_cpu = _network_to_numpy(target)
    cpu_opts = dict(compress_opts)
    cpu_opts.pop("method", None)
    result_cpu = operator_cpu.apply(
        target_cpu,
        compress=compress,
        contract=contract,
        **cpu_opts,
    )
    try:
        return _network_to_torch(result_cpu, device, dtype)
    except Exception as exc:
        if not _is_torch_oom_error(exc):
            raise
        _clear_torch_cache()
        warnings.warn(
            "Tensor-network CPU fallback result does not fit back on GPU; "
            "keeping this result on CPU.",
            RuntimeWarning,
            stacklevel=2,
        )
        return result_cpu

def apply_mpo(mpo1: MatrixProductOperator, mpo2: MatrixProductOperator,
                side,
                max_bond=None,
                cutoff=0.0,
                contract=True,
                compress=True,
                **compress_opts):
    if side == "right":
        return stable_apply_operator(
            mpo1,
            mpo2,
            compress=compress,
            max_bond=max_bond,
            cutoff=cutoff,
            contract=contract,
            create_bond=True,
            **compress_opts,
        )
    elif side == "left":
        return stable_apply_operator(
            mpo2,
            mpo1,
            compress=compress,
            max_bond=max_bond,
            cutoff=cutoff,
            contract=contract,
            create_bond=True,
            **compress_opts,
        )
    else:
        raise ValueError("side must be 'left' or 'right'.")



# ------------------------------------------------------------------
#  Applying circuits to MPO
# ------------------------------------------------------------------


def apply_circuit(mpo, circ, side, max_bond=None, cutoff=0.0, contract=True, compress=True, **compress_opts):
    return apply_mpo(mpo, mpo_from_circuit(circ), side=side, max_bond=max_bond, cutoff=cutoff, contract=contract, compress=compress, **compress_opts)


def apply_swaps(mpo: MatrixProductOperator, swaps_l, swaps_r, max_bond=None, cutoff=0.0, to_backend=None, inplace=False):
    N = len(mpo.sites)
    qc_swaps_l = QuantumCircuit(N)
    qc_swaps_r = QuantumCircuit(N)

    for q0, q1 in swaps_l:
        qc_swaps_l.swap(q0, q1)

    for q0, q1 in swaps_r:
        qc_swaps_r.swap(q0, q1)

    mpo_out = mpo if inplace else mpo.copy()

    if len(swaps_l) > 0:
        circ_l = quimb_circuit(qc_swaps_l.inverse().decompose("swap"), Circuit, to_backend=to_backend)
        mpo_out = apply_circuit(mpo_out, circ_l, side="right", max_bond=max_bond, cutoff=cutoff)
    
    if len(swaps_r) > 0:
        circ_r = quimb_circuit(qc_swaps_r.decompose("swap"), Circuit, to_backend=to_backend)
        mpo_out = apply_circuit(mpo_out, circ_r, side="left", max_bond=max_bond, cutoff=cutoff) 

    return mpo_out
