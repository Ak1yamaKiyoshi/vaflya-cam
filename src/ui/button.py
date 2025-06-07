import cv2 as cv
import numpy as np

class Button:
    def __init__(self, x, y, width, height, text, color=(100, 100, 100), rotation=0, callback=None):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.text, self.color, self.rotation, self.callback = text, color, rotation, callback
        self.is_pressed = False
        
    def is_inside(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height
    
    def on_press(self):
        self.is_pressed = True
        if self.callback:
            self.callback(self.text)
    
    def on_release(self):
        self.is_pressed = False
    
    def draw(self, canvas):
        if self.rotation == 0:
            cv.rectangle(canvas, (self.x, self.y), (self.x + self.width, self.y + self.height), self.color, -1)
            cv.rectangle(canvas, (self.x, self.y), (self.x + self.width, self.y + self.height), (200, 200, 200), 2)
            self.draw_text(canvas)
        else:
            center = (self.x + self.width//2, self.y + self.height//2)
            M = cv.getRotationMatrix2D(center, self.rotation, 1.0)
            corners = np.array([[self.x, self.y], [self.x + self.width, self.y], 
                               [self.x + self.width, self.y + self.height], [self.x, self.y + self.height]])
            rotated = cv.transform(corners.reshape(1, -1, 2), M).reshape(-1, 2).astype(int)
            cv.fillPoly(canvas, [rotated], self.color)
            cv.polylines(canvas, [rotated], True, (200, 200, 200), 2)
            self.draw_rotated_text(canvas, center, M)
    
    def draw_text(self, canvas):
        font, scale, thickness = cv.FONT_HERSHEY_SIMPLEX, 0.6, 2
        (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
        tx = self.x + (self.width - tw) // 2
        ty = self.y + (self.height + th) // 2
        cv.putText(canvas, self.text, (tx, ty), font, scale, (255, 255, 255), thickness)
    
    def draw_rotated_text(self, canvas, center, M):
        font, scale, thickness = cv.FONT_HERSHEY_SIMPLEX, 0.6, 2
        (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
        text_center = np.array([center[0] - tw//2, center[1] + th//2])
        rotated_pos = cv.transform(text_center.reshape(1, 1, 2), M).reshape(2).astype(int)
        
        temp_canvas = np.zeros_like(canvas)
        cv.putText(temp_canvas, self.text, (center[0] - tw//2, center[1] + th//2), 
                   font, scale, (255, 255, 255), thickness)
        rotated_text = cv.warpAffine(temp_canvas, M, (canvas.shape[1], canvas.shape[0]))
        mask = rotated_text > 0
        canvas[mask] = rotated_text[mask]