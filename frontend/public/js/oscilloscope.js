/**
 * Real-Time Canvas Oscilloscope.
 * Renders high-fidelity sweep waveforms for ECG, PPG, EDA, and Respiration at 60fps.
 */

class MissionOscilloscope {
  constructor(canvasId, channel = 'ECG', options = {}) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.channel = channel;
    this.color = options.color || '#00E5FF';
    this.sampleRate = options.sampleRate || 256;
    this.buffer = new Float32Array(512);
    this.writeIndex = 0;
    this.sweepX = 0;
    this.sweepSpeed = options.sweepSpeed || 2.5; // pixels per frame
    this.minVal = options.minVal || -2.5;
    this.maxVal = options.maxVal || 2.5;
    this.history = [];
    this.isRunning = true;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.render();
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    this.width = rect.width * (window.devicePixelRatio || 1);
    this.height = rect.height * (window.devicePixelRatio || 1);
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.history = new Array(Math.ceil(this.width)).fill(this.height / 2);
  }

  pushData(samples) {
    if (!samples || samples.length === 0) return;
    for (const val of samples) {
      // Map val to canvas Y
      const norm = (val - this.minVal) / (this.maxVal - this.minVal);
      const y = this.height - (norm * this.height * 0.85 + this.height * 0.075);
      this.buffer[this.writeIndex % this.buffer.length] = y;
      this.writeIndex++;
    }
  }

  render() {
    if (!this.isRunning) return;

    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;

    // Fade background to create phosphor persistence
    ctx.fillStyle = 'rgba(5, 11, 24, 0.25)';
    ctx.fillRect(0, 0, w, h);

    // Draw grid lines
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = 0; x < w; x += 40) { ctx.moveTo(x, 0); ctx.lineTo(x, h); }
    for (let y = 0; y < h; y += 30) { ctx.moveTo(0, y); ctx.lineTo(w, y); }
    ctx.stroke();

    // Baseline center
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.15)';
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();

    // Advance sweep
    const steps = Math.floor(this.sweepSpeed * (window.devicePixelRatio || 1));
    for (let i = 0; i < steps; i++) {
      const targetX = (this.sweepX + i) % w;
      const sampleY = this.buffer[(this.writeIndex - 1) % this.buffer.length] || (h / 2);
      this.history[targetX] = sampleY;
    }

    // Draw waveform trace
    ctx.strokeStyle = this.color;
    ctx.lineWidth = 1.8 * (window.devicePixelRatio || 1);
    ctx.shadowBlur = 8;
    ctx.shadowColor = this.color;
    ctx.beginPath();

    let started = false;
    for (let x = 0; x < w; x++) {
      if (Math.abs(x - this.sweepX) < 15) {
        started = false;
        continue;
      }
      const y = this.history[x] || (h / 2);
      if (!started) {
        ctx.moveTo(x, y);
        started = true;
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Sweep cursor bar
    ctx.fillStyle = 'rgba(0, 229, 255, 0.4)';
    ctx.fillRect(this.sweepX, 0, 3, h);

    this.sweepX = (this.sweepX + steps) % w;
    requestAnimationFrame(() => this.render());
  }
}

window.MissionOscilloscope = MissionOscilloscope;
