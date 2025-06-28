import cv2 as cv
import numpy as np
import time

class Button:
    def __init__(self, x, y, width, height, text, color=(100, 100, 100), rotation=0, callback=None, toggle_mode=False, transparent=False, transparent_style=0):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.text, self.color, self.rotation, self.callback = text, color, rotation, callback
        self.is_pressed = False
        self.toggle_mode = toggle_mode
        self.is_toggled = False 
        self.transparent = transparent
        self.transparent_style = transparent_style
        self.original_color = color
        self.toggled_color = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50))
        self.pressed_color = (max(0, color[0] - 80), max(0, color[1] - 80), max(0, color[2] - 80))
        self.press_time = 0
        self.press_duration = 0.1
        
    def is_inside(self, x, y):
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height
    
    def on_press(self):
        if not self.toggle_mode:
            self.is_pressed = True
            self.press_time = time.time()
        else:
            self.is_toggled = not self.is_toggled
        
        if self.callback:
            if self.toggle_mode:
                self.callback(self.text, self.is_toggled)
            else:
                self.callback(self.text)
    
    def on_release(self):
        if not self.toggle_mode:  
            self.is_pressed = False
    
    def update(self):
        if not self.toggle_mode and self.is_pressed:
            if time.time() - self.press_time > self.press_duration:
                self.is_pressed = False
    
    def get_current_color(self):
        if not self.toggle_mode and self.is_pressed:
            return self.pressed_color
        elif self.toggle_mode and self.is_toggled:
            return self.toggled_color
        return self.original_color
    
    def get_text_color(self):
        if self.transparent:
            if not self.toggle_mode and self.is_pressed:
                return (int(self.original_color[0] * 0.2), 
                       int(self.original_color[1] * 0.2), 
                       int(self.original_color[2] * 0.2))
            elif self.toggle_mode and self.is_toggled:
                return self.original_color
            elif self.transparent_style == 0:  # Border style - darken when inactive
                return (int(self.original_color[0] * 0.4), 
                       int(self.original_color[1] * 0.4), 
                       int(self.original_color[2] * 0.4))
            else:  # Style 1 (blur) - bright when not toggled, dark when toggled off
                if self.toggle_mode and not self.is_toggled:
                    return (int(self.original_color[0] * 0.4), 
                           int(self.original_color[1] * 0.4), 
                           int(self.original_color[2] * 0.4))
                return self.original_color
        return (255, 255, 255)
    
    def apply_blur_effect(self, canvas):
        if self.rotation == 0:
            roi = canvas[self.y:self.y + self.height, self.x:self.x + self.width]
            if roi.size > 0:
                blur_amount = (71, 71) if self.is_pressed else (51, 51)
                blurred = cv.GaussianBlur(roi, blur_amount, 0)
                if self.is_pressed:
                    blurred = blurred * 0.5
                canvas[self.y:self.y + self.height, self.x:self.x + self.width] = blurred
        else:
            center = (self.x + self.width//2, self.y + self.height//2)
            M = cv.getRotationMatrix2D(center, self.rotation, 1.0)
            corners = np.array([[self.x, self.y], [self.x + self.width, self.y], 
                               [self.x + self.width, self.y + self.height], [self.x, self.y + self.height]])
            rotated = cv.transform(corners.reshape(1, -1, 2), M).reshape(-1, 2).astype(int)
            
            mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
            cv.fillPoly(mask, [rotated], 255)
            
            blurred_canvas = cv.GaussianBlur(canvas, (15, 15), 0)
            canvas[mask > 0] = blurred_canvas[mask > 0]
    
    def draw(self, canvas):
        self.update()
        
        if self.transparent:
            if self.transparent_style == 0:
                border_color = (255, 255, 255)
                if self.rotation == 0:
                    cv.rectangle(canvas, (self.x, self.y), (self.x + self.width, self.y + self.height), border_color, 2)
                    self.draw_text(canvas)
                else:
                    center = (self.x + self.width//2, self.y + self.height//2)
                    M = cv.getRotationMatrix2D(center, self.rotation, 1.0)
                    corners = np.array([[self.x, self.y], [self.x + self.width, self.y], 
                                       [self.x + self.width, self.y + self.height], [self.x, self.y + self.height]])
                    rotated = cv.transform(corners.reshape(1, -1, 2), M).reshape(-1, 2).astype(int)
                    cv.polylines(canvas, [rotated], True, border_color, 2)
                    self.draw_rotated_text(canvas, center, M)
            
            elif self.transparent_style == 1:
                self.apply_blur_effect(canvas)
                self.draw_text(canvas) if self.rotation == 0 else self.draw_rotated_text(canvas, 
                    (self.x + self.width//2, self.y + self.height//2), 
                    cv.getRotationMatrix2D((self.x + self.width//2, self.y + self.height//2), self.rotation, 1.0))
        else:
            current_color = self.get_current_color()
            
            if self.rotation == 0:
                cv.rectangle(canvas, (self.x, self.y), (self.x + self.width, self.y + self.height), current_color, -1)
                border_color = (255, 255, 255) if (self.toggle_mode and self.is_toggled) else (200, 200, 200)
                cv.rectangle(canvas, (self.x, self.y), (self.x + self.width, self.y + self.height), border_color, 2)
                self.draw_text(canvas)
            else:
                center = (self.x + self.width//2, self.y + self.height//2)
                M = cv.getRotationMatrix2D(center, self.rotation, 1.0)
                corners = np.array([[self.x, self.y], [self.x + self.width, self.y], 
                                   [self.x + self.width, self.y + self.height], [self.x, self.y + self.height]])
                rotated = cv.transform(corners.reshape(1, -1, 2), M).reshape(-1, 2).astype(int)
                cv.fillPoly(canvas, [rotated], current_color)
                border_color = (255, 255, 255) if (self.toggle_mode and self.is_toggled) else (200, 200, 200)
                cv.polylines(canvas, [rotated], True, border_color, 2)
                self.draw_rotated_text(canvas, center, M)
    
    def draw_text(self, canvas):
        font, scale, thickness = cv.FONT_HERSHEY_DUPLEX, 0.5, 1
        (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
        tx = self.x + (self.width - tw) // 2
        ty = self.y + (self.height + th) // 2
        text_color = self.get_text_color()
        cv.putText(canvas, self.text, (tx, ty), font, scale, text_color, thickness)
    
    def draw_rotated_text(self, canvas, center, M):
        font, scale, thickness = cv.FONT_HERSHEY_DUPLEX, 0.5, 1
        (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
        text_center = np.array([center[0] - tw//2, center[1] + th//2])
        rotated_pos = cv.transform(text_center.reshape(1, 1, 2), M).reshape(2).astype(int)
        
        temp_canvas = np.zeros_like(canvas)
        text_color = self.get_text_color()
        cv.putText(temp_canvas, self.text, (center[0] - tw//2, center[1] + th//2), 
                   font, scale, text_color, thickness)
        rotated_text = cv.warpAffine(temp_canvas, M, (canvas.shape[1], canvas.shape[0]))
        mask = rotated_text > 0
        canvas[mask] = rotated_text[mask]