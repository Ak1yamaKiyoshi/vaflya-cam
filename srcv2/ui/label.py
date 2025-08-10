import cv2 as cv
import numpy as np

class Label:
   def __init__(self, x, y, width, height, text, color=(255, 255, 255), rotation=0, size=0.5):
       self.x, self.y, self.width, self.height = x, y, width, height
       self.text, self.color, self.rotation, self.size = text, color, rotation, size
       self.original_color = color
   
   def update_text(self, text):
       self.text = text    
   
   def draw(self, canvas):
       if self.rotation == 0:
           self.draw_text(canvas)
       else:
           center = (self.x + self.width//2, self.y + self.height//2)
           M = cv.getRotationMatrix2D(center, self.rotation, 1.0)
           self.draw_rotated_text(canvas, center, M)

   def draw_text(self, canvas):
       font, scale, thickness = cv.FONT_HERSHEY_DUPLEX, self.size, 1
       (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
       tx = self.x + (self.width - tw) // 2
       ty = self.y + (self.height + th) // 2
       cv.putText(canvas, self.text, (tx, ty), font, scale, self.original_color, thickness)

   def draw_rotated_text(self, canvas, center, M):
       font, scale, thickness = cv.FONT_HERSHEY_DUPLEX, self.size, 1
       (tw, th), _ = cv.getTextSize(self.text, font, scale, thickness)
       temp_canvas = np.zeros_like(canvas)
       cv.putText(temp_canvas, self.text, (center[0] - tw//2, center[1] + th//2), 
                   font, scale, self.original_color, thickness)
       rotated_text = cv.warpAffine(temp_canvas, M, (canvas.shape[1], canvas.shape[0]))
       mask = rotated_text > 0
       canvas[mask] = rotated_text[mask]