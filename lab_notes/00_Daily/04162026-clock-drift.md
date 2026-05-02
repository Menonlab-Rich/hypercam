### Problem Summary
The current display-based setup fails because the event camera and the display computer operate on independent oscillators. Cumulative **clock drift** means that a timestamp $t$ on the sensor does not correspond to the same instant $t$ in the Pygame logic, making it impossible to accurately map event coordinates to ground-truth pixel positions.

---

### Proposed Solutions

#### 1. Synchronized Dual-Camera System (Frame + Event)
* **Why it addresses the problem:** It replaces the software-based "source of truth" with a hardware-based one that can be physically linked to the sensor.
* **How it works:** By using a hardware trigger or a shared sync cable, both cameras capture data on the same temporal grid. The frame-based camera provides absolute $x,y$ coordinates for the object. As long as the object velocity stays below the frame-based camera's motion-blur threshold, the frames serve as a reliable spatial reference for the events occurring between those frames.

![[Pasted image 20260417105800.png]]

#### 2. External High-Precision Tracking (OptiTrack or GPS)
* **Why it addresses the problem:** It uses a specialized reference system designed specifically to minimize jitter and drift across high-speed measurements.
* **How it works:** Systems like GPS or IR-based motion capture provide timestamps and spatial coordinates with much higher resolution than the event sensor's latency. The high temporal resolution allows you to characterize and subtract the drift of the event camera clock relative to the "global" time of the tracking system.
![[Pasted image 20260417110209.png]]
#### 3. Precision Time Protocol (PTP) Synchronization
* **Why it addresses the problem:** It forces the computer's system clock to align its frequency with the camera's internal hardware clock.
* **How it works:** By setting the event camera as the PTP master, the host computer’s clock is constantly adjusted to match the camera's oscillator. This eliminates the frequency mismatch (drift). While a constant phase offset (latency) may remain, it is a static value that can be calibrated once, unlike drift which changes over time.
![[Pasted image 20260417110748.png]]
#### 4. Pre-labeled Datasets
* **Why it addresses the problem:** It removes the need for real-time synchronization during the testing phase.
* **How it works:** Using datasets where the ground truth is already verified and synchronized allows you to isolate and test the tracking algorithm's logic. However, this is a limited solution as it does not allow for testing physical variables like specific lens working distances (WD) or the effects of your custom phase masks.

#### 5. Deterministic Mechanical Motion (Spinning Motor)
* **Why it addresses the problem:** It removes the need to synchronize two devices by making the ground truth a function of the event camera’s own clock.
* **How it works:** A motor at steady-state rotational frequency $f$ is highly stable. The position of an object on the motor at any time $t$ can be calculated via:
$$P(t) = A \cos(2\pi f t + \phi)$$
Because $f$ is constant, you only need to determine the initial phase $\phi$ at one point in time. Once $\phi$ is known, the ground truth position is calculated using the **event camera’s own timestamps**, meaning the "source of truth" and the "sensor data" are natively on the same clock.
![[Pasted image 20260417112453.png]]
#### 6. Software Alignment
* **Why it addresses the problem:** We programatically align the desynchronized data allowing us to treat the data as correctly aligned.
* **How it works:** We use computer vision techniques to find the best candidate for the $t=0$ and $t=\text{end}$ values. This is imprecise but does let us make use of the desynchronized data.

