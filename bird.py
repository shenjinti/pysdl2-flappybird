"""The Flappybird Game."""

import sys
import sdl2
import sdl2.ext
import time
import math
import random
from easing_functions import easing

WIDTH = 480
HEIGHT = 640

IMGS = sdl2.ext.Resources(__file__, "img")
BLACK = sdl2.ext.Color(0, 0, 0)
BIRD_SIZE = (92, 64)
SCALE = WIDTH/768

MODE_SCALE = 0
MODE_TILE = 1
SCROLL_DIRECTION = (-4, 0)

EVENT_START_GAME = sdl2.events.SDL_USEREVENT + 1
EVENT_PLAY_GAME = sdl2.events.SDL_USEREVENT + 2
EVENT_END_GAME = sdl2.events.SDL_USEREVENT + 3

FRAME_COST = 1 / 60.0


class Tile:
    def __init__(self, sprite, x=0, y=0):
        self.fill_mode = MODE_SCALE
        self.sprite = sprite
        self.texture = sprite.texture
        self._scale = 1
        self.depth = 0
        self._x = x
        self._y = y
        self._size = sprite.size
        self._w, self._h = self._size

        self.angle = 0.0
        self.flip = sdl2.render.SDL_FLIP_NONE

        self.src = sdl2.rect.SDL_Rect(0, 0, self._w, self._h)
        self.dest = sdl2.rect.SDL_Rect(x, y, self._w, self._h)
        self.actions = []

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self._x = value
        self.dest.x = value

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self._y = value
        self.dest.y = value

    @property
    def w(self):
        return self._w

    @property
    def h(self):
        return self._h

    @property
    def position(self):
        return self._x, self._y

    @position.setter
    def position(self, value):
        self._x, self._y = value
        self.dest.x, self.dest.y = value

    @property
    def size(self):
        return self._w, self._h

    @size.setter
    def size(self, value):
        if value == self._size:
            return
        self._size = value
        self._calc_size()

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        if value == self._scale:
            return
        self._scale = value
        self._calc_size()

    def _calc_size(self):
        self._w = int(self._size[0] * self._scale)
        self._h = int(self._size[1] * self._scale)
        self.dest.w, self.dest.h = self._w, self._h

    def process(self, delta):
        pass

    def animation(self, delta):
        for obj in self.actions:
            if obj.check_ticks(delta) is False:
                continue
            obj.do_animation(self, delta)

    def add_animator(self, anim, unique=False):
        if hasattr(anim, "do_animation") is False:
            raise Exception("Invalid animator")
        if unique:
            for i in range(len(self.actions)):
                if type(self.actions[i]) == type(anim):
                    del self.actions[i]
                    break

        self.actions.append(anim)

    def fill(self):
        rects = []

        x = self.src.x
        y = self.src.y

        fill_x = self.dest.x
        fill_y = self.dest.y

        w, h = self.fill_size

        while fill_x < w:
            fill_src = sdl2.rect.SDL_Rect(
                self.src.x, self.src.y, self.src.w, self.src.h)
            fill_dest = sdl2.rect.SDL_Rect(
                fill_x, fill_y, self.dest.w, self.dest.h)
            fill_x += self.dest.w
            rects.append((fill_src, fill_dest))

        while fill_y < h:
            fill_src = sdl2.rect.SDL_Rect(
                self.src.x, self.src.y, self.src.w, self.src.h)
            fill_dest = sdl2.rect.SDL_Rect(
                fill_x, fill_y, self.dest.w, self.dest.h)
            fill_y += self.dest.h
            rects.append((fill_src, fill_dest))

        return rects


class Scene:
    def __init__(self, factory):
        self.factory = factory
        self.objects = set([])
        self._last_process_ticks = time.time()

    def add_object(self, obj):
        self.objects.add(obj)

    def remove_object(self, obj):
        self.objects.remove(obj)

    def process(self):
        now = time.time()
        delta = now - self._last_process_ticks
        self.process_objects(delta)
        self.process_animation(delta)
        self._last_process_ticks = now

    def process_animation(self, delta):
        for obj in self.objects:
            obj.animation(delta)

    def process_objects(self, delta):
        for obj in self.objects:
            obj.process(delta)

    def keydown(self, sym):
        pass

    def keyup(self, sym):
        pass


class SceneRenderSystem:
    def __init__(self, renderer):
        self.sdlrenderer = renderer.sdlrenderer

    def render(self, scene):
        objs = sorted(scene.objects, key=lambda x: x.depth)
        rcopy = sdl2.render.SDL_RenderCopyEx
        renderer = self.sdlrenderer

        for obj in objs:
            if obj.fill_mode == MODE_SCALE:
                if rcopy(renderer, obj.texture, obj.src, obj.dest, obj.angle,
                         None, obj.flip) == -1:
                    raise sdl2.SDLError()
            elif obj.fill_mode == MODE_TILE:
                rects = obj.fill()
                for r in rects:
                    if rcopy(renderer, obj.texture, r[0], r[1], obj.angle,
                             None, obj.flip) == -1:
                        raise sdl2.SDLError()

        sdl2.render.SDL_RenderPresent(renderer)


class Animator:
    def __init__(self):
        self._ticks = 0
        self._last_ticks = 0
        self.interval = 0.01

    def check_ticks(self, delta):
        self._ticks += delta
        if self._last_ticks != 0 and  \
                self._ticks - self._last_ticks < self.interval:
            return False

        self._last_ticks = self._ticks

        return True


class TextureAnimator(Animator):
    def __init__(self):
        super(TextureAnimator, self).__init__()

        self._frame_count = 0
        self.frame_rects = []

    def do_animation(self, tile, delta):
        size = len(self.frame_rects)
        if size < 1:
            return

        self._frame_count += 1
        if self._frame_count > 65535:
            self._frame_count = 0
        rect = self.frame_rects[self._frame_count % size]
        tile.src.x, tile.src.y, tile.src.w, tile.src.h = rect
        tile.size = (rect[2], rect[3])


class ScrollAnimator(Animator):
    def __init__(self):
        super(ScrollAnimator, self).__init__()

        self.area = sdl2.rect.SDL_Rect(0, 0, 0, 0)
        self.direction = (0, 0)
        self.repeat = True

    def do_animation(self, tile, delta):

        tile.dest.x += self.direction[0]
        tile.dest.y += self.direction[1]

        if self.repeat is False:
            return

        if self.direction[0] < 0:
            if tile.dest.x + tile.dest.w < self.area.x:
                tile.dest.x = self.area.w
        else:
            if tile.dest.x >= self.area.w:
                tile.dest.x = self.area.x

        if self.direction[1] < 0:
            if tile.dest.y + tile.dest.h < self.area.y:
                tile.dest.y = self.area.h
        else:
            if tile.dest.y > self.area.h:
                tile.dest.y = self.area.y


class PathAnimator(Animator):
    def __init__(self):
        super(PathAnimator, self).__init__()
        self.emit = None

    def do_animation(self, tile, delta):
        if self.emit is None:
            return

        point = self.emit.next(self, tile, delta)
        if point is None:
            return

        tile.dest.x, tile.dest.y = point


class EllipseEmit:
    def __init__(self, ew, eh):
        self.ew = ew
        self.eh = eh
        self.angle = 0
        self.step = 4

    def next(self, animator, tile, delta):
        pos = tile.position
        #t = self.angle * math.pi / 180
        t = math.radians(self.angle)
        point = (
            pos[0] + int(math.cos(t) * self.ew),
            pos[1] + int(math.sin(t) * self.eh)
        )
        self.angle += self.step
        if self.angle >= 360:
            self.angle = 0
        return point


class EasingIter:
    def __init__(self, obj, param, target, func, duration):
        def update_param(obj, param, value):
            orig_type = type(getattr(obj, param))
            setattr(obj, param, orig_type(value))

        self._update = lambda _x: update_param(obj, param, _x)
        self._value = lambda: getattr(obj, param)
        self._target = target
        self._duration = duration / 1000.0
        self._func = func
        self._expend = 0.0
        self.is_done = False
        self._ease_func = None

    def update(self, delta):
        if self._ease_func is None:
            self._ease_func = self._func(
                start=self._value(), end=self._target, duration=1)

        self._expend += delta

        if self._expend >= self._duration:
            self.is_done = True

        ratio = self._expend / self._duration
        v = self._ease_func.ease(ratio)
        self._update(v)
        return True


class EasingEmit:
    """
        `attrs`:
            * x, y, angle, alpha, scale
        usage:
        emit = EasingEmit()
        emit.linear({"x": 100}, 200)
        emit.quad_in({"y":200, "x": 300}, 100)
        emit.wait(200)
        emit.quad_out({"y": 100}, 200)
        emit.wait()

    """

    def __init__(self, animator):
        self.chains = []
        self._animator = animator

    def next(self, animator, tile, delta):

        while len(self.chains) > 0:
            chain = self.chains[0]

            updated = chain.update(delta)

            if chain.is_done:
                self.chains.pop(0)
                continue
            break

    def clear(self):
        self.chains = []

    def wait(self, duration=0.0):
        # self._to({})
        pass

    def _to(self, attrs, duration, func):
        for (attr, target) in attrs.items():
            easingit = EasingIter(self._animator, attr,
                                  target, func, duration)
            self.chains.append(easingit)

    def linear(self, attrs, duration):
        self._to(attrs, duration, easing.LinearInOut)

    def quad_in(self, attrs, duration):
        self._to(attrs, duration, easing.QuadEaseIn)

    def quad_out(self, attrs, duration):
        self._to(attrs, duration, easing.SineEaseOut)

    def quad_in_out(self, attrs, duration):
        self._to(attrs, duration, easing.QuadEaseInOut)


class Bird(Tile):
    def __init__(self, sprite):
        super(Bird, self).__init__(sprite)


class Pipe(Tile):
    def __init__(self, sprite):
        super(Pipe, self).__init__(sprite)


class Floor(Tile):
    def __init__(self, sprite):
        super(Floor, self).__init__(sprite)

        anim = ScrollAnimator()
        anim.direction = SCROLL_DIRECTION
        anim.area = sdl2.rect.SDL_Rect(
            0, self.position[1], self.position[0], HEIGHT)
        self.add_animator(anim)

        self.fill_mode = MODE_TILE
        self.fill_size = (WIDTH, self.position[1])


class SceneResource:
    def loadResource(self):
        img_background = self.factory.from_image(
            IMGS.get_path("background.png"))
        img_birds = self.factory.from_image(IMGS.get_path("bird.png"))
        img_floor = self.factory.from_image(IMGS.get_path("ground.png"))

        background = Tile(img_background)
        background.depth = -1
        background.scale = SCALE

        self.add_object(background)

        floor = Floor(img_floor)
        floor.position = (0, HEIGHT - int(img_floor.size[1] * SCALE))
        floor.depth = 3
        floor.scale = SCALE

        self.floor = floor

        self.add_object(floor)

        self.bird = Bird(img_birds)
        self.bird.depth = 1
        self.bird.scale = SCALE
        self.bird.position = (int((WIDTH)/2) - self.bird.size[1], 200)
        self.add_object(self.bird)


class StartScene(Scene, SceneResource):
    def __init__(self, factory):
        super(StartScene, self).__init__(factory)
        self.loadResource()

        anim = TextureAnimator()
        anim.interval = 0.1
        anim.frame_rects = [
            (BIRD_SIZE[0], 0, BIRD_SIZE[0], BIRD_SIZE[1]),
        ]
        self.bird.add_animator(anim)

        anim = PathAnimator()
        anim.emit = EllipseEmit(0, 10)
        anim.emit.step = 4
        self.bird.add_animator(anim)

    def keydown(self, sym):
        if sym == sdl2.SDLK_SPACE:
            ev = sdl2.events.SDL_Event()
            ev.type = EVENT_PLAY_GAME
            sdl2.events.SDL_PushEvent(ev)


class PlayScene(Scene, SceneResource):
    def __init__(self, factory):
        Scene.__init__(self, factory)
        self.loadResource()

        anim = TextureAnimator()
        anim.interval = 0.1
        anim.frame_rects = [
            (0, 0, BIRD_SIZE[0], BIRD_SIZE[1]),
            (BIRD_SIZE[0], 0, BIRD_SIZE[0], BIRD_SIZE[1]),
            (BIRD_SIZE[0]*2, 0, BIRD_SIZE[0], BIRD_SIZE[1]),
        ]
        self.bird.add_animator(anim)

        self.is_stop = False
        self.colddown = 3
        self.pipes = set([])
        self.img_pipe = factory.from_image(IMGS.get_path("pipe.png"))
        
        self.do_jump()

    def process_objects(self, delta):
        super(PlayScene, self).process_objects(delta)

        if self.is_stop is True:
            return

        self.check_pipes(delta)
        self.check_bird_collision(delta)

    def check_pipes(self, delta):
        if self.is_stop is True:
            return

        def check_bound(p):
            return p.dest.x + p.dest.w <= 0

        outs = [p for p in self.pipes if check_bound(p)]

        for p in outs:
            self.pipes.remove(p)
            self.remove_object(p)

        self.colddown -= delta
        if self.colddown <= 0:
            self.gen_pipe()
            self.colddown = 2

    def gen_pipe(self):
        fixed_height = 50

        up_pipe = Pipe(self.img_pipe)

        up_pipe.scale = SCALE
        up_pipe.flip = sdl2.render.SDL_FLIP_VERTICAL
        up_pipe.depth = 2

        down_pipe = Pipe(self.img_pipe)
        down_pipe.scale = SCALE
        down_pipe.depth = 2

        mid_y = int(random.randint(180, 340))

        up_pos = (WIDTH, mid_y - fixed_height - 560)
        up_pipe.position = up_pos

        down_pos = (WIDTH, mid_y + fixed_height)
        down_pipe.position = down_pos

        anim = ScrollAnimator()
        anim.direction = SCROLL_DIRECTION
        anim.area = sdl2.rect.SDL_Rect(0, up_pos[1], WIDTH, HEIGHT)
        anim.repeat = False

        up_pipe.add_animator(anim)

        anim = ScrollAnimator()
        anim.direction = SCROLL_DIRECTION
        anim.area = sdl2.rect.SDL_Rect(0, down_pos[1], WIDTH, HEIGHT)
        anim.repeat = False

        down_pipe.add_animator(anim)

        self.pipes.add(up_pipe)
        self.pipes.add(down_pipe)

        self.add_object(up_pipe)
        self.add_object(down_pipe)

    def keydown(self, sym):
        if sym != sdl2.SDLK_SPACE:
            return

        if self.is_stop:
            ev = sdl2.events.SDL_Event()
            ev.type = EVENT_PLAY_GAME
            sdl2.events.SDL_PushEvent(ev)
            return

        self.do_jump()

    def do_jump(self):
        anim = PathAnimator()
        anim.emit = EasingEmit(self.bird)

        if self.bird.y <= - BIRD_SIZE[1]:
            self.bird.y = - BIRD_SIZE[1]

        jump_amount = 60
        jump_time = 180

        y = self.bird.y
        anim.emit.linear({"y": self.bird.y - jump_amount}, jump_time)
        anim.emit.quad_in({"y": y + 150}, jump_time * 2.5)
        anim.emit.linear({"y": HEIGHT}, (HEIGHT - (y + 200)))

        self.bird.add_animator(anim, True)

    def check_bird_collision(self, delta):
        if self.bird.y + self.bird.size[1] >= self.floor.y:
            self.game_over()
            return

        for p in self.pipes:
            if self.bird.dest.x < p.dest.x + p.w and \
                    self.bird.dest.x + self.bird.w > p.dest.x and \
                    self.bird.dest.y < p.dest.y + p.h and \
                    self.bird.dest.y + self.bird.h > p.dest.y:
                self.game_over()
                break

    def game_over(self):
        self.is_stop = True
        #self.remove_object(self.bird)

        self.bird.actions = []

        self.floor.actions = []

        for p in self.pipes:
            p.actions = []


def run():
    sdl2.ext.init()
    window = sdl2.ext.Window("The Flappybird Game", size=(WIDTH, HEIGHT))
    window.show()

    renderer = sdl2.ext.Renderer(
        window, flags=sdl2.render.SDL_RENDERER_PRESENTVSYNC)

    factory = sdl2.ext.SpriteFactory(sdl2.ext.TEXTURE, renderer=renderer)
    scenerenderer = SceneRenderSystem(renderer)
    scene = StartScene(factory)

    running = True
    while running:
        for event in sdl2.ext.get_events():
            if event.type == sdl2.SDL_QUIT:
                running = False
                break
            if event.type == sdl2.SDL_KEYDOWN:
                scene.keydown(event.key.keysym.sym)
            elif event.type == sdl2.SDL_KEYUP:
                scene.keyup(event.key.keysym.sym)
            elif event.type == EVENT_START_GAME:
                scene = StartScene(factory)
            elif event.type == EVENT_PLAY_GAME:
                scene = PlayScene(factory)
            elif event.type == EVENT_END_GAME:
                scene = EndScene(factory)

        scene.process()
        scenerenderer.render(scene)

        sdl2.SDL_Delay(16)


if __name__ == "__main__":
    run()
