"""Linear-counting sketches (Kamp et al., 2013) for privacy-preserving overlap counts.

A sensor never sends IDs: it sends R bit-arrays of M bits, each built with its own
salted hash. Union = bitwise OR, overlap = inclusion-exclusion.
"""
import hashlib

import numpy as np

M, R = 128, 16


def hash_positions(ids, salt, m=M, r=R):
    # bit position of every id in each of the r sketches (r x len(ids))
    out = np.empty((r, len(ids)), np.int32)
    for k in range(r):
        for j, i in enumerate(ids):
            h = hashlib.sha256(f"{salt}|{k}|{int(i)}".encode()).digest()
            out[k, j] = int.from_bytes(h[:4], "little") % m
    return out


def build(positions, member, m=M):
    # member: bool mask over the ids that positions was built for
    sk = np.zeros((positions.shape[0], m), bool)
    for k in range(positions.shape[0]):
        sk[k, positions[k, member]] = True
    return sk


def estimate(sk):
    # mean of the per-sketch maximum-likelihood estimates, -m ln(zeros/m)
    m = sk.shape[1]
    zeros = np.maximum((~sk).sum(1), 0.5)
    return float(np.mean(-m * np.log(zeros / m)))


def overlap(sk_a, sk_b):
    return max(0.0, estimate(sk_a) + estimate(sk_b) - estimate(sk_a | sk_b))
