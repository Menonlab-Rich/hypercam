pub mod macros;
pub mod traits;

use dfdx::prelude::*;
use traits::TransposeExt;

// Define your sensor resolution once
type Resolution = (Const<640>, Const<480>);
type EventPacket<const BATCH: usize> = Tensor<(Const<BATCH>, usize, Const<2>), f32, AutoDevice>;

fn main() {
    let dev = AutoDevice::default();

    // Now your initialization is extremely clean:
    let x: EventPacket<10> = dev.zeros_like(&(Const, 500, Const));
    let y: EventPacket<10> = make_tensor!(dev, EventPacket<10>, 500);
    let _y = y.t();
    let xy = x.matmul(_y);
    dbg!(xy);
}
