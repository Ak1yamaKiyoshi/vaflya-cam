import cv2 as cv

class Slider:
    def __init__(self, x, y, width, min_val, max_val, initial_val, text, callback=None):
        self.x, self.y, self.width = x, y, width
        self.min_val, self.max_val = min_val, max_val
        self.value = initial_val
        self.text, self.callback = text, callback
        self.dragging = False
        self.drag_start_val, self.drag_start_x = 0, 0
    
    def value_to_x(self, val):
        return self.x + int((val - self.min_val) / (self.max_val - self.min_val) * self.width)
    
    def x_to_value(self, x):
        ratio = max(0, min(1, (x - self.x) / self.width))
        return self.min_val + ratio * (self.max_val - self.min_val)
    
    def is_inside(self, x, y):
        return self.x <= x <= self.x + self.width and self.y - 15 <= y <= self.y + 25
    
    def start_drag(self, x):
        self.dragging = True
        self.drag_start_val, self.drag_start_x = self.value, x
    
    def update_drag(self, x):
        if self.dragging:
            old_value = self.value
            delta_x = x - self.drag_start_x
            delta_val = (delta_x / self.width) * (self.max_val - self.min_val)
            self.value = max(self.min_val, min(self.max_val, self.drag_start_val + delta_val))
            if self.callback and abs(self.value - old_value) > 0.01:
                self.callback(self.text, self.value)
    
    def set_value(self, new_value):
        old_value = self.value
        self.value = max(self.min_val, min(self.max_val, new_value))
        if self.callback and abs(self.value - old_value) > 0.01:
            self.callback(self.text, self.value)
    
    def end_drag(self):
        self.dragging = False
    
    def draw(self, canvas):
        # Draw slider track with black outline
        for i in range(0, self.width, 10):
            # Black outline (+1x, +1y offset)
            cv.line(canvas, (self.x + i + 1, self.y + 1), (self.x + i + 5 + 1, self.y + 1), (0, 0, 0), 1)
            # White fill
            cv.line(canvas, (self.x + i, self.y), (self.x + i + 5, self.y), (100, 100, 100), 1)
        
        # Draw vertical line marker (|) instead of X
        cross_x = self.value_to_x(self.value)
        # Black outline (+1x, +1y offset)
        cv.line(canvas, (cross_x + 1, self.y - 8 + 1), (cross_x + 1, self.y + 8 + 1), (0, 0, 0), 3)
        # White fill
        cv.line(canvas, (cross_x, self.y - 8), (cross_x, self.y + 8), (255, 255, 255), 2)
        
        # Draw text with black outline
        # Black outline (+1x, +1y offset)
        cv.putText(canvas, f"{self.text}: {self.value:.1f}", 
                  (self.x + 1, self.y - 15 + 1), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        # White fill
        cv.putText(canvas, f"{self.text}: {self.value:.1f}", 
                  (self.x, self.y - 15), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)