"""Categorised deformation metric (replaces the folded-face count for judging; the legacy count is kept alongside).
Events are counted relative to the rest pose (an event already present at rest, e.g. touching fingers, is not new).
Region: vertices within REGION of the pose's focus joint (rest positions), head cavities excluded.

  contact        vertex lies 0..CONTACT in front of a DISTANT face (normal crease contact; informational)
  intersection   a mesh EDGE passes through a DISTANT triangle (exact segment/triangle test): skin passed through skin.
                 Reported: intersecting quads, and the max depth of vertices behind the other surface that are
                 connected to an actual crossing (isolated 'behind a plane' cases are not intersections)
  fold_over      interior edge whose two quads face nearly opposite ways (dihedral > FOLDOVER deg): surface doubled back
  pinch          new sharp bend (dihedral grows by > PINCH deg) on an edge NOT in a contact/intersection zone
  crease_line    the same sharp bend INSIDE a contact/intersection zone: the normal line of a crease (informational)
  stretch        edge strain p95 / p5 and share of quads whose area grew > 1.5x or shrank < 0.6x
'DISTANT' = farther than LOCAL at rest from the vertex (so a face's own neighbourhood never counts as contact)."""
import numpy as np, collections
REGION, LOCAL, CONTACT, DEPTH, FOLDOVER, PINCH = 0.25, 0.020, 0.002, 0.050, 150.0, 60.0

def _quad_normals(X, Q):
    n = np.cross(X[Q[:, 2]] - X[Q[:, 0]], X[Q[:, 3]] - X[Q[:, 1]]); return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-15)

class Metric2:
    def __init__(self, V, Q, exclude):
        self.V, self.Q, self.ex = V, Q, exclude
        self.T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
        fe = collections.defaultdict(list)
        for fi, q in enumerate(Q):
            for k in range(4): a, b = q[k], q[(k + 1) % 4]; fe[(min(a, b), max(a, b))].append(fi)
        E = [(e, f) for e, f in fe.items() if len(f) == 2]
        self.E = np.array([e for e, _ in E]); self.EF = np.array([f for _, f in E])
        self.E_all = np.array(list(fe.keys()))
        self.dih0 = self._dihedral(V)
        self.rest = None

    def _dihedral(self, X):
        n = _quad_normals(X, self.Q); return np.degrees(np.arccos(np.clip((n[self.EF[:, 0]] * n[self.EF[:, 1]]).sum(1), -1, 1)))

    @staticmethod
    def _join(P, rad, lo, hi):
        """Candidate pairs (point i, box j) with point inside box j inflated by rad, via a hashed grid."""
        cs = max(rad, 0.01); key = lambda k: (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
        vk = key(np.floor(P / cs).astype(np.int64)); order = np.argsort(vk); vkeys = vk[order]
        flo = np.floor((lo - rad) / cs).astype(np.int64); fhi = np.floor((hi + rad) / cs).astype(np.int64)
        span = (fhi - flo).max(0) + 1; pv, pf = [], []
        for dx in range(span[0]):
            for dy in range(span[1]):
                for dz in range(span[2]):
                    k = flo + [dx, dy, dz]; ok = np.all(k <= fhi, 1); kk = key(k[ok]); fi = np.where(ok)[0]
                    l = np.searchsorted(vkeys, kk, 'left'); r = np.searchsorted(vkeys, kk, 'right'); cnt = r - l; m = cnt > 0
                    if not m.any(): continue
                    rep = np.repeat(np.arange(m.sum()), cnt[m]); starts = np.repeat(l[m], cnt[m])
                    off = np.arange(len(rep)) - np.repeat(np.cumsum(cnt[m]) - cnt[m], cnt[m])
                    pv.append(order[starts + off]); pf.append(fi[m][rep])
        if not pv: return np.zeros(0, int), np.zeros(0, int)
        return np.concatenate(pv), np.concatenate(pf)

    def _distant(self, vi, t):
        V0 = self.V
        d0 = np.min(np.stack([np.linalg.norm(V0[vi] - V0[t[:, k]], axis=1) for k in range(3)], 1), 1)
        return (d0 > LOCAL) & ~np.any(t == vi[:, None], 1)

    def _proximity(self, X, verts, faces, edges):
        T = self.T[faces]; A, B, C = X[T[:, 0]], X[T[:, 1]], X[T[:, 2]]
        lo = np.minimum(np.minimum(A, B), C); hi = np.maximum(np.maximum(A, B), C)
        n = np.cross(B - A, C - A); n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-15)[:, None]
        def vertex_vs_faces(vs, rad):
            pv, pf = self._join(X[vs], rad, lo, hi)
            k = self._distant(vs[pv], T[pf]); pv, pf = pv[k], pf[k]
            p = X[vs[pv]]; a = A[pf]; nn = n[pf]
            d = ((p - a) * nn).sum(1); q = p - d[:, None] * nn
            v0, v1, v2 = B[pf] - a, C[pf] - a, q - a
            d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
            den = np.maximum(d00 * d11 - d01 * d01, 1e-30); w1 = (d11 * d20 - d01 * d21) / den; w2 = (d00 * d21 - d01 * d20) / den
            return vs[pv], d, (w1 >= 0) & (w2 >= 0) & (w1 + w2 <= 1)
        front = np.full(len(self.V), np.inf); behind = np.zeros(len(self.V))
        vi, d, inside = vertex_vs_faces(verts, CONTACT)                  # contact: small radius only
        m = inside & (d >= 0) & (d <= CONTACT); np.minimum.at(front, vi[m], d[m])
        # 2. exact: mesh edge vs distant triangle (Moller-Trumbore, 0 <= t <= 1)
        E = edges; P0, P1 = X[E[:, 0]], X[E[:, 1]]
        mid = (P0 + P1) / 2; half = np.linalg.norm(P1 - P0, axis=1).max() / 2
        pe, pf2 = self._join(mid, half, lo, hi)
        k = self._distant(E[pe, 0], T[pf2]) & self._distant(E[pe, 1], T[pf2]); pe, pf2 = pe[k], pf2[k]
        o = P0[pe]; dvec = P1[pe] - o; a = A[pf2]; e1 = B[pf2] - a; e2 = C[pf2] - a
        h = np.cross(dvec, e2); det = (e1 * h).sum(1); ok = np.abs(det) > 1e-14; inv = np.where(ok, 1 / np.where(ok, det, 1), 0)
        sv = o - a; u = (sv * h).sum(1) * inv; qv = np.cross(sv, e1); v = (dvec * qv).sum(1) * inv; t = (e2 * qv).sum(1) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)
        crossing = np.zeros(len(self.V), bool); crossing[E[pe[hit]].ravel()] = True; crossing[T[pf2[hit]].ravel()] = True
        if crossing.any():                                              # depth: only near actual crossings
            cv = np.where(crossing)[0]; ck, _ = self._join(X[verts], DEPTH, X[cv], X[cv])
            near = verts[np.unique(ck)]
            vi, d, inside = vertex_vs_faces(near, DEPTH)
            m = inside & (d < 0) & (-d <= DEPTH); np.maximum.at(behind, vi[m], -d[m])
        return front, behind, crossing

    def events(self, X, centre):
        reg = (np.linalg.norm(self.V - centre, axis=1) < REGION) & ~self.ex
        verts = np.where(reg)[0]
        faces = np.where(reg[self.T].all(1))[0]
        ereg_e = self.E_all[reg[self.E_all].all(1)]
        front, behind, crossing = self._proximity(X, verts, faces, ereg_e)
        # intersection zone: crossing vertices, grown through connected 'behind' vertices (depth measured there)
        inter = crossing & reg; grow = (behind > 0) & reg
        while True:
            nb = np.zeros(len(self.V), bool); m = inter[self.E_all[:, 0]] | inter[self.E_all[:, 1]]
            nb[self.E_all[m].ravel()] = True; new = nb & grow & ~inter
            if not new.any(): break
            inter |= new
        contact = np.isfinite(front) & reg & ~inter; dep = np.where(inter, behind, 0.0)
        dih = self._dihedral(X)
        ereg = reg[self.E].all(1)
        return dict(reg=reg, ereg=ereg, contact=contact, inter=inter, depth=dep, dih=dih)

    def measure(self, Xp, centre):
        if self.rest is None or self.rest[0] is not centre:
            self.rest = (centre, self.events(self.V, centre))
        r = self.rest[1]; p = self.events(Xp, centre)
        new_contact = p['contact'] & ~r['contact'] & ~r['inter']; new_inter = p['inter'] & ~r['inter']
        zone = new_contact | new_inter | p['contact'] | p['inter']
        # grow the zone by one ring so the crease line itself (between two contacting sides) is in it
        zr = zone.copy(); zr[self.E[zone[self.E[:, 0]] | zone[self.E[:, 1]]].ravel()] = True
        sharp = p['ereg'] & (p['dih'] - self.dih0 > PINCH)
        in_zone = zr[self.E].any(1)
        fold = p['ereg'] & (p['dih'] > FOLDOVER) & ~(self.dih0 > FOLDOVER)
        # stretch / area
        Q = self.Q; rq = p['reg'][Q].all(1)
        e = lambda X, a, b: np.linalg.norm(X[Q[:, a]] - X[Q[:, b]], axis=1)
        st = np.concatenate([e(Xp, a, b) / np.maximum(e(self.V, a, b), 1e-12) for a, b in ((0, 1), (1, 2), (2, 3), (3, 0))]).reshape(4, -1)[:, rq].ravel()
        area = lambda X: 0.5 * np.linalg.norm(np.cross(X[Q[:, 2]] - X[Q[:, 0]], X[Q[:, 3]] - X[Q[:, 1]]), axis=1)
        ar = area(Xp)[rq] / np.maximum(area(self.V)[rq], 1e-15)
        qi = new_inter[self.Q].any(1) & p['reg'][self.Q].all(1)
        return {'contact_vertices': int(new_contact.sum()),
                'intersection_vertices': int(new_inter.sum()), 'intersection_quads': int(qi.sum()), 'intersection_max_depth_mm': round(float(p['depth'][new_inter].max() * 1000) if new_inter.any() else 0.0, 1),
                'fold_over_edges': int(fold.sum()),
                'pinch_edges': int((sharp & ~in_zone).sum()), 'pinch_length_mm': round(float(np.linalg.norm(Xp[self.E[sharp & ~in_zone, 0]] - Xp[self.E[sharp & ~in_zone, 1]], axis=1).sum() * 1000), 1),
                'crease_line_edges': int((sharp & in_zone).sum()),
                'strain_p95': round(float(np.percentile(st, 95)), 3), 'strain_p5': round(float(np.percentile(st, 5)), 3),
                'area_grow_pct': round(float((ar > 1.5).mean() * 100), 1), 'area_shrink_pct': round(float((ar < 0.6).mean() * 100), 1)}
