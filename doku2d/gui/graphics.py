from ..core import Signal
from .base import Control
from .theme import box, texture


class Panel(Control):
    def render(self,target,states):
        box(target,states,(0,0,*self.size),self.theme.surface,self.theme.border,radius=self.theme.radius+4)


class NinePatchRect(Control):
    texture_changed = Signal()

    def __init__(self,name=None):
        super().__init__(name)
        self._texture = None
        self._draw_center = True
        self._region_rect = [0,0,0,0]
        self._patch_margin = [8,8,8,8]
        self.mouse_filter = "ignore"

    @property
    def texture(self):
        return self._texture

    @texture.setter
    def texture(self,value):
        if self._texture is not value:
            self._texture = value
            self.texture_changed.emit()

    def render(self,target,states):
        if self.texture is None:
            box(target,states,(0,0,*self.size),self.theme.surface,self.theme.border)
            return
        sx,sy,sw,sh = self.region_rect
        if not sw or not sh: sx,sy,sw,sh = 0,0,self.texture.size.x,self.texture.size.y
        left,top,right,bottom = [max(0,float(value)) for value in self.patch_margin]
        factor_x = min(1,sw/max(1,left+right))
        factor_y = min(1,sh/max(1,top+bottom))
        left,right = left*factor_x,right*factor_x
        top,bottom = top*factor_y,bottom*factor_y
        dx = min(1,self.size.x/max(1,left+right))
        dy = min(1,self.size.y/max(1,top+bottom))
        source_x = [sx,sx+left,sx+sw-right,sx+sw]
        source_y = [sy,sy+top,sy+sh-bottom,sy+sh]
        dest_x = [0,left*dx,self.size.x-right*dx,self.size.x]
        dest_y = [0,top*dy,self.size.y-bottom*dy,self.size.y]
        for row in range(3):
            for column in range(3):
                if not self.draw_center and row == column == 1: continue
                region = (source_x[column],source_y[row],source_x[column+1]-source_x[column],source_y[row+1]-source_y[row])
                rect = (dest_x[column],dest_y[row],dest_x[column+1]-dest_x[column],dest_y[row+1]-dest_y[row])
                if region[2] > 0 and region[3] > 0 and rect[2] > 0 and rect[3] > 0:
                    texture(target,states,self.texture,rect,region)


    @property
    def draw_center(self):
        return self._draw_center

    @draw_center.setter
    def draw_center(self, value):
        self._draw_center = value

    @property
    def region_rect(self):
        return self._region_rect

    @region_rect.setter
    def region_rect(self, value):
        self._region_rect = value

    @property
    def patch_margin(self):
        return self._patch_margin

    @patch_margin.setter
    def patch_margin(self, value):
        self._patch_margin = value
