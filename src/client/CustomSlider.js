export class CustomSlider extends HTMLElement {
  constructor() {
    super();
    this.viewportWidth = parseInt(this.getAttribute('viewport-width')) || 250;
    this.multiplier = parseInt(this.getAttribute('multiplier')) || 3;
    this.minValue = parseFloat(this.getAttribute('min-value')) || 0.000125;
    this.maxValue = parseFloat(this.getAttribute('max-value')) || 32;
    this.isLogarithmic = this.getAttribute('logarithmic') === 'true' || true; // Default to logarithmic
    this.tickDensity = parseInt(this.getAttribute('tick-density')) || 10;
    this.bodyWidth = this.viewportWidth * this.multiplier;
    this.velocity = 0; this.animationId = null; this.isDragging = false;
    this.startPosition = 0; this.currentLeft = 0; this.lastX = 0; this.lastMoveTime = 0;
    // Remove lastSetValue from constructor
    
    this._initStyles();
    this.render();
    this.setupEventListeners();
  }
  
  _initStyles() {
    if (!document.getElementById('custom-slider-styles')) {
      const style = document.createElement('style');
      style.id = 'custom-slider-styles';
      style.textContent = `
        custom-slider { display: block; position: relative; margin: 20px 0; }
        .slider-viewport { overflow: hidden; position: relative; background: #f5f5f5; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
        .slider-body { height: 30px; background: #f9f9f9; position: relative; display: flex; align-items: center; touch-action: none; }
        .vertical-bar { width: 1px; height: 15px; background: #aaa; position: relative; margin-top: 8px; border-radius: 1px; }
        .vertical-bar.major { height: 22px; width: 2px; background: #666; margin-top: 4px; border-radius: 1px; }
        .bar-label { position: absolute; bottom: -15px; transform: translateX(-50%); font-size: 9px; color: #666; }
        .center-marker { position: absolute; width: 0; height: 0; left: 50%; z-index: 10; transform: translateX(-50%); }
        .marker-top { top: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #3498db; }
        .marker-bottom { bottom: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 5px solid #3498db; }
      `;
      document.head.appendChild(style);
    }
  }
  
  render() {
    this.viewport = document.createElement('div');
    this.viewport.className = 'slider-viewport';
    this.viewport.style.width = `${this.viewportWidth}px`;
    
    this.sliderBody = document.createElement('div');
    this.sliderBody.className = 'slider-body';
    this.sliderBody.style.width = `${this.bodyWidth}px`;
    this.sliderBody.style.left = '0px';
    
    const values = this.generateValues();
    const barSpacing = this.bodyWidth / (values.length - 1);
    
    for (let i = 0; i < values.length; i++) {
      const bar = document.createElement('div');
      bar.className = 'vertical-bar' + (i % 2 === 0 ? ' major' : '');
      bar.style.left = `${i * barSpacing}px`;
      
      if (i % 2 === 0) {
        const label = document.createElement('div');
        label.className = 'bar-label';
        label.textContent = this.formatValue(values[i]);
        bar.appendChild(label);
      }
      this.sliderBody.appendChild(bar);
    }
    
    const markerTop = document.createElement('div');
    markerTop.className = 'center-marker marker-top';
    
    const markerBottom = document.createElement('div');
    markerBottom.className = 'center-marker marker-bottom';
    
    this.viewport.appendChild(this.sliderBody);
    this.viewport.appendChild(markerTop);
    this.viewport.appendChild(markerBottom);
    this.appendChild(this.viewport);
  }
  
  generateValues() {
    if (this.isLogarithmic) {
      const values = [];
      const minLog = Math.log10(this.minValue);
      const maxLog = Math.log10(this.maxValue);
      const step = (maxLog - minLog) / this.tickDensity;
      
      for (let log = minLog; log <= maxLog; log += step) {
        values.push(Math.pow(10, log));
      }
      return values;
    } else {
      const values = [];
      const range = this.maxValue - this.minValue;
      const step = range / this.tickDensity;
      
      for (let val = this.minValue; val <= this.maxValue; val += step) {
        values.push(val);
      }
      return values;
    }
  }
  
  formatValue(value) {
    if (value < 0.001) return value.toExponential(1);
    if (value < 0.01) return value.toFixed(3);
    if (value < 0.1) return value.toFixed(2);
    if (value < 1) return value.toFixed(2);
    if (value < 10) return value.toFixed(1);
    return value.toFixed(0);
  }
  
  setupEventListeners() {
    // Mouse events
    this.sliderBody.addEventListener('mousedown', e => {
      this.startDrag(e.clientX);
      e.preventDefault();
    });
    
    // Add event listeners to document to handle mouse moves outside the slider
    document.addEventListener('mousemove', e => {
      if (this.isDragging) {
        this.processDrag(e.clientX);
      }
    });
    
    document.addEventListener('mouseup', () => {
      this.endDrag();
    });
    
    // Touch events
    this.sliderBody.addEventListener('touchstart', e => {
      this.startDrag(e.touches[0].clientX);
      e.preventDefault();
    });
    
    document.addEventListener('touchmove', e => {
      if (this.isDragging) {
        this.processDrag(e.touches[0].clientX);
        e.preventDefault();
      }
    });
    
    document.addEventListener('touchend', () => {
      this.endDrag();
    });
    
    document.addEventListener('touchcancel', () => {
      this.endDrag();
    });
  }
  
  startDrag(clientX) {
    this.isDragging = true;
    this.startPosition = clientX;
    this.currentLeft = parseInt(this.sliderBody.style.left) || 0;
    this.lastMoveTime = 0;
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    this.velocity = 0;
    // We no longer clear lastSetValue here
  }
  
  processDrag(clientX) {
    if (!this.isDragging) return;
    
    const currentTime = Date.now();
    const delta = clientX - this.startPosition;
    const newLeft = this.currentLeft + delta;
    
    const maxRight = 0;
    const maxLeft = -(this.bodyWidth - this.viewportWidth);
    
    // Constrain the position to the slider bounds
    const constrainedLeft = Math.min(maxRight, Math.max(maxLeft, newLeft));
    this.sliderBody.style.left = `${constrainedLeft}px`;
    
    // Calculate velocity only if we're within bounds
    if (constrainedLeft <= maxRight && constrainedLeft >= maxLeft) {
      if (this.lastMoveTime > 0) {
        const dt = currentTime - this.lastMoveTime;
        if (dt > 0) {
          const dx = clientX - this.lastX;
          this.velocity = dx / dt * 15;
        }
      }
    }
    
    this.lastX = clientX;
    this.lastMoveTime = currentTime;
    this.dispatchSliderEvent();
  }
  
  endDrag() {
    if (!this.isDragging) return;
    
    this.isDragging = false;
    this.currentLeft = parseInt(this.sliderBody.style.left) || 0;
    
    if (Math.abs(this.velocity) > 0.1) {
      this.animationId = requestAnimationFrame(this.applyInertia.bind(this));
    }
  }
  
  applyInertia() {
    const currentLeft = parseInt(this.sliderBody.style.left) || 0;
    let newLeft = currentLeft + this.velocity;
    
    const maxRight = 0;
    const maxLeft = -(this.bodyWidth - this.viewportWidth);
    
    if (newLeft > maxRight) { newLeft = maxRight; this.velocity = 0; }
    if (newLeft < maxLeft) { newLeft = maxLeft; this.velocity = 0; }
    
    this.sliderBody.style.left = `${newLeft}px`;
    this.velocity *= 0.95;
    
    if (Math.abs(this.velocity) < 0.1) {
      this.velocity = 0;
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    } else {
      this.animationId = requestAnimationFrame(this.applyInertia.bind(this));
    }
    
    this.dispatchSliderEvent();
  }
  
  getCurrentPercentage() {
    const currentLeft = parseInt(this.sliderBody.style.left) || 0;
    const maxLeft = -(this.bodyWidth - this.viewportWidth);
    const percentage = Math.abs(currentLeft / maxLeft);
    return Math.min(1, Math.max(0, percentage));
  }
  
  getCurrentValue() {
    // Note: We no longer use lastSetValue here directly since it was causing resets
    const percentage = this.getCurrentPercentage();
    
    if (this.isLogarithmic) {
      const minLog = Math.log10(this.minValue);
      const maxLog = Math.log10(this.maxValue);
      const log = minLog + percentage * (maxLog - minLog);
      return Math.pow(10, log);
    } else {
      return this.minValue + percentage * (this.maxValue - this.minValue);
    }
  }
  
  dispatchSliderEvent() {
    const currentValue = this.getCurrentValue();
    const formattedValue = this.formatValue(currentValue);
    
    this.dispatchEvent(new CustomEvent('slider-change', {
      bubbles: true,
      detail: {
        percentage: this.getCurrentPercentage() * 100,
        value: currentValue,
        formattedValue: formattedValue
      }
    }));
  }
  
  // Public API methods
  setValue(value) {
    // No longer storing lastSetValue
    
    let percentage;
    if (this.isLogarithmic) {
      const minLog = Math.log10(this.minValue);
      const maxLog = Math.log10(this.maxValue);
      const valueLog = Math.log10(value);
      percentage = (valueLog - minLog) / (maxLog - minLog);
    } else {
      percentage = (value - this.minValue) / (this.maxValue - this.minValue);
    }
    
    percentage = Math.min(1, Math.max(0, percentage));
    const maxLeft = -(this.bodyWidth - this.viewportWidth);
    const newLeft = -percentage * Math.abs(maxLeft);
    
    this.sliderBody.style.left = `${newLeft}px`;
    this.dispatchSliderEvent();
  }
  
  // Add a new method specifically for the updateValue API call
  updateValue(value) {
    this.setValue(value);
  }
}

// Register the custom element
customElements.define('custom-slider', CustomSlider);