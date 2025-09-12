from ..rotation3d import *
import numpy as np
import torch

q = torch.from_numpy(np.array([[0, 1, 2, 3], [-2, 3, -1, 5]], dtype=np.float32))
print("q", q)
r = quat_normalize(q)
x = torch.from_numpy(np.array([[1, 0, 0], [0, -1, 0]], dtype=np.float32))
print(r)
print(quat_rotate(r, x))

angle = torch.from_numpy(np.array(np.random.rand() * 10.0, dtype=np.float32))
axis = torch.from_numpy(
    np.array([1, np.random.rand() * 10.0, np.random.rand() * 10.0], dtype=np.float32),
)

print(repr(angle))
print(repr(axis))

rot = quat_from_angle_axis(angle, axis)
x = torch.from_numpy(np.random.rand(5, 6, 3))
y = quat_rotate(quat_inverse(rot), quat_rotate(rot, x))
print(x.numpy())
print(y.numpy())
assert np.allclose(x.numpy(), y.numpy())

m = torch.from_numpy(np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=np.float32))
r = quat_from_rotation_matrix(m)
t = torch.from_numpy(np.array([0, 1, 0], dtype=np.float32))
se3 = transform_from_rotation_translation(r=r, t=t)
print(se3)
print(transform_apply(se3, t))

rot = quat_from_angle_axis(
    torch.from_numpy(np.array([45, -54], dtype=np.float32)),
    torch.from_numpy(np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)),
    degree=True,
)
trans = torch.from_numpy(np.array([[1, 1, 0], [1, 1, 0]], dtype=np.float32))
transform = transform_from_rotation_translation(r=rot, t=trans)

t = transform_mul(transform, transform_inverse(transform))
gt = np.zeros((2, 7))
gt[:, 0] = 1.0
print(t.numpy())
print(gt)
# assert np.allclose(t.numpy(), gt)

transform2 = torch.from_numpy(
    np.array(
        [[1, 0, 0, 1], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dtype=np.float32
    ),
)
transform2 = euclidean_to_transform(transform2)
print(transform2)
