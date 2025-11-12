## 1. Coordinate Transform (World → Local)

Convert any world point **x** into the local span coordinate system:

$$
\begin{bmatrix}
u\\
v\\
w
\end{bmatrix}=
\begin{bmatrix}
\hat{\mathbf{u}}^{\top}\\
\hat{\mathbf{v}}^{\top}\\
\hat{\mathbf{w}}'^{\top}
\end{bmatrix}
(\mathbf{x}-\mathbf{p}_A)
$$

Span length:

$$
L = u(\mathbf{p}_B)
$$

---

## 2. Mean Intersection-over-Union (mIoU)

For class \( c \):

$$
\mathrm{IoU}_c = \frac{\mathrm{TP}_c}{\mathrm{TP}_c+\mathrm{FP}_c+\mathrm{FN}_c}
$$

Mean IoU:

$$
\mathrm{mIoU} = \frac{1}{|\mathcal{C}|}\sum_{c\in\mathcal{C}}\mathrm{IoU}_c
$$

---

## 3. Hausdorff Distance

$$
d_{\mathrm H}(\mathcal{P},\mathcal{G})=
\max\{
\max_{\mathbf{p}\in\mathcal{P}}\min_{\mathbf{g}\in\mathcal{G}}\|\mathbf{p}-\mathbf{g}\|,
\max_{\mathbf{g}\in\mathcal{G}}\min_{\mathbf{p}\in\mathcal{P}}\|\mathbf{g}-\mathbf{p}\|
\}
$$

This distance measures the worst-case spatial deviation between predicted and ground-truth polylines.

---

## 4. Catenary Wire Model

Equation of a hanging wire in local coordinates:

$$
w(u) = w_0 + a \cosh\!\big((u-u_0)/a\big)
$$

Sag (vertical drop):

$$
\mathrm{sag} = \max\{w(0),w(L)\} - w(u_0)
$$

Approximate tension:

$$
T_0 = a \mu g
$$

Arc length between \(u_1\) and \(u_2\):

$$
\mathcal{L}(u_1,u_2) = a \sinh\!\big((u-u_0)/a\big)\Big|_{u_1}^{u_2}
$$

---

## 5. Parabolic Wire Approximation

Used if data points are insufficient for full catenary fitting.

$$
w(u) = \alpha u^2 + \beta u + \gamma
$$

Vertex and sag:

$$
u_v = -\frac{\beta}{2\alpha}, \quad
\mathrm{sag} =
\begin{cases}
\max\{w(0), w(L)\} - w(u_v), & 0 \le u_v \le L \\
|w(0) - w(L)|, & \text{otherwise}
\end{cases}
$$

Arc length:

$$
\mathcal{L} =
\int_0^{L}\sqrt{1+(2\alpha u+\beta)^2}\,du=
\frac{(2\alpha u+\beta)\sqrt{1+(2\alpha u+\beta)^2}}{4\alpha}\Big|_0^{L}
+
\frac{\sinh^{-1}(2\alpha u+\beta)}{4\alpha}\Big|_0^{L}
$$

---

## 6. Tower Axis and Tilt

Covariance of tower points:

$$
\mathbf{C} = \frac{1}{M}\sum_{j=1}^{M}(\mathbf{t}_j - \bar{\mathbf{t}})(\mathbf{t}_j - \bar{\mathbf{t}})^\top
$$

Principal eigenvector \( \mathbf{e}_{\max} \) gives the tower’s main axis.

Tilt from vertical:

$$
\theta_{\mathrm{tilt}} = \arccos\!\Big(\frac{|\,\mathbf{e}_{\max}\cdot\hat{\mathbf{z}}\,|}{\|\mathbf{e}_{\max}\|}\Big) \times \frac{180}{\pi}
$$

---

## 7. Clearance Check

Vertical clearance at location \((X,Y)\):

$$
\Delta h(X,Y) = Z_{\mathrm{wire}}(X,Y) - Z_{\mathrm{DTM}}(X,Y)
$$

Minimum clearance along span:

$$
\Delta h_{\min} = \min_{u\in[0,L]} \big( Z_{\mathrm{wire}}(u) - Z_{\mathrm{DTM}}(X(u),Y(u)) \big)
$$

Violation if \( \Delta h_{\min} < h_{\min}^{\text{reg}} \).

---

## 8. Segmentation Loss Functions

Weighted cross-entropy:

$$
\mathcal{L}_{\mathrm{CE}} = -\frac{1}{N}\sum_{i=1}^{N}\sum_{c} w_c\, y_{ic} \log p_{ic}
$$

Focal loss:

$$
\mathcal{L}_{\mathrm{FL}} = -\sum_{c}\alpha_c (1 - p_{ic})^{\gamma} y_{ic} \log p_{ic}
$$

Combined loss:

$$
\mathcal{L} = \lambda_{\mathrm{CE}}\mathcal{L}_{\mathrm{CE}} + \lambda_{\mathrm{FL}}\mathcal{L}_{\mathrm{FL}}
$$

---


## 9. Similarity Transform (AP → ALS Registration)

Estimate scale \(s\), rotation \(R\), and translation \(t\):

$$
\min_{s, R, t} \sum_k \| \mathbf{b}_k - (s R \mathbf{a}_k + t) \|^2
$$

Closed-form solution using SVD of the cross-covariance matrix between matched points.


---


## Summary Table

| Section | Concept | Primary Output |
|----------|----------|----------------|
| 1 | Coordinate Transform | Local span coordinates |
| 2 | mIoU | Segmentation accuracy |
| 3 | Hausdorff Distance | Geometric deviation |
| 4 | Catenary Model | Wire sag & tension |
| 5 | Parabolic Approximation | Fallback geometry |
| 6 | Tower Axis & Tilt | Structural alignment |
| 7 | Clearance Check | Ground-wire clearance |
| 8 | Loss Functions | Stable segmentation training |
| 9 | Similarity Transform | Aligned dataset |

---
