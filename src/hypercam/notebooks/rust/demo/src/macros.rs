#[macro_export]
macro_rules! make_tensor {
    // For aliases with one dynamic dimension: build_tensor!(dev, Alias, dynamic_val)
    ($dev:expr, $alias:ty, $dyn:expr) => {
        $dev.zeros_like(&(Const, $dyn, Const))
    };
    // For fully static aliases: build_tensor!(dev, Alias)
    ($dev:expr, $alias:ty) => {
        $dev.zeros::<$alias, f32, _>()
    };
}
