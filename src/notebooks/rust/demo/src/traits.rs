use dfdx::prelude::*;

pub trait TransposeExt {
    type Output;
    fn t(self) -> Self::Output;
}

// Implementation for 2D Tensors: (M, N) -> (N, M)
impl<M: Dim, N: Dim, E: Dtype, D: Device<E>, T: Tape<E, D>> TransposeExt
    for Tensor<(M, N), E, D, T>
{
    type Output = Tensor<(N, M), E, D, T>;

    fn t(self) -> Self::Output {
        self.permute::<_, Axes2<1, 0>>()
    }
}

// Implementation for 3D Batched Tensors: (B, M, N) -> (B, N, M)
impl<B: Dim, M: Dim, N: Dim, E: Dtype, D: Device<E>, T: Tape<E, D>> TransposeExt
    for Tensor<(B, M, N), E, D, T>
{
    type Output = Tensor<(B, N, M), E, D, T>;

    fn t(self) -> Self::Output {
        self.permute::<_, Axes3<0, 2, 1>>()
    }
}
