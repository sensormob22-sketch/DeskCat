"""Per-clip clocks; inactive clips freeze, incoming clips align before blending."""
import math


class ClipClock:
    def __init__(self, durations):
        if any(not math.isfinite(d) or d <= 0 for d in durations.values()):
            raise ValueError('Clip durations must be finite and positive')
        self.durations = dict(durations)
        self.times = dict.fromkeys(durations, 0.0)
        self.previous_weights = dict.fromkeys(durations, 0.0)
        self.speed = 1.0
        self.paused = False

    def seek(self, clip, seconds):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Clip time must be finite and nonnegative')
        self.times[clip] = seconds % self.durations[clip]

    def update(self, dt, weights):
        if not math.isfinite(dt) or dt < 0 or not math.isfinite(self.speed) or self.speed < 0:
            raise ValueError('dt and playback speed must be finite and nonnegative')
        active = {c: float(weights.get(c, 0)) for c in self.durations}
        outgoing = [c for c in self.durations if self.previous_weights[c] > 0]
        reference = max(outgoing, key=self.previous_weights.get) if outgoing else None
        # Align only before first contribution. Never reset a visible clip,
        # including when an in-progress crossfade is interrupted.
        phase = self.times[reference] / self.durations[reference] if reference else None
        for clip, weight in active.items():
            if weight > 0 and self.previous_weights[clip] == 0 and phase is not None:
                self.times[clip] = phase * self.durations[clip]
        if not self.paused:
            for clip, weight in active.items():
                if weight > 0:
                    self.times[clip] = (self.times[clip] + dt*self.speed) % self.durations[clip]
        self.previous_weights = active
        return self.times.copy()
