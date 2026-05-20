// event-tracker-python.cpp
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include "event-tracker.h"
#include "metavision/sdk/base/events/event_cd.h"

namespace py = pybind11;

// Wrapper function to handle the NumPy memory directly
py::tuple process_events_wrapper(Metavision::EventClusterTracker &tracker,
                                 py::array_t<Metavision::EventCD> input_np) {
  // Request raw memory access
  auto input_buf = input_np.request();
  auto *input_ptr = static_cast<Metavision::EventCD *>(input_buf.ptr);
  size_t count = input_buf.shape[0];

  // Allocate output arrays
  py::array_t<Metavision::EventCD> output_cd(count);
  py::array_t<int> output_ids(count);

  auto *out_cd_ptr =
      static_cast<Metavision::EventCD *>(output_cd.request().ptr);
  auto *out_id_ptr = static_cast<int *>(output_ids.request().ptr);

  // Process and populate
  for (size_t i = 0; i < count; ++i) {
    tracker.process_single_event(input_ptr[i]);
    out_cd_ptr[i] = input_ptr[i]; // Passthrough event
    out_id_ptr[i] = tracker.get_pixel_cluster(input_ptr[i].x, input_ptr[i].y);
  }

  return py::make_tuple(output_cd, output_ids);
}

PYBIND11_MODULE(event_cluster_tracker, m) {
  py::class_<Metavision::EventClusterTracker>(m, "EventClusterTracker")
      .def(py::init<int, int, Metavision::timestamp>(), py::arg("width"),
           py::arg("height"), py::arg("dt_threshold"))

      // Bind our custom wrapper instead of the generic helpers
      .def("process_events", &process_events_wrapper, py::arg("input_np"))

      .def("get_pixel_cluster",
           &Metavision::EventClusterTracker::get_pixel_cluster, py::arg("x"),
           py::arg("y"));
}
