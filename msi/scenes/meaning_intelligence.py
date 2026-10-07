"""meaning_intelligence.py —— MSI 六层演示动画 / Six-Act Scene

每一幕对应六层应用栈的一层，逐幕推进：

  Act 1  减负            120 个随机粒子收敛为 12 个结构节点
  Act 2  可体验          出现可操作控件，节点随参数实时重排
  Act 3  意义生成        节点归位到 方向·价值·边界 三角
  Act 4  价值评估        每个节点套上 E0–E6 证据色环，并给出证据色阶
  Act 5  方向选择        三条候选路径，两条淡出，一条高亮为选定方向
  Act 6  反思与审视递归  螺旋回写至同角度的更高起点 L1'

运行（在 msi/ 目录下）：
    manim -ql scenes/meaning_intelligence.py MeaningIntelligenceScene

已避开的 Manim 陷阱（均经实测确认）：
  · 同一个 mobject 在同一 play() 里挂两个动画，后写入者会逐帧覆盖先写入者
    （曾导致 60 个 Rotate 全部失效、有/无该动画渲染出的 MP4 逐像素相同）。
    本文件不做这种叠加。
  · 若把 updater 逐个挂到 N 个 mobject 上并共享累加器，累加器每帧会被累加 N 次，
    进度会在 1/N 的时长内跑满。本文件只在 VGroup 上挂一个组级 updater，
    并用场景时钟 / 控件位置算进度，天然幂等。
  · ParametricFunction 默认 use_vectorized=False，必须以标量 t 调用并返回 (x, y, z) 三元组。
"""
import json
import sys
from pathlib import Path

# 允许从 msi/ 直接运行：把 msi/ 加入模块搜索路径（manim 只会加入 scenes/）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from manim import *  # noqa: F403

from mi_common import (BASE_DIR, LAYER_ORDER, enable_utf8_console, get_cjk_font,
                       load_config, safe_print)

enable_utf8_console()

CONFIG = load_config()
FONT = get_cjk_font()
THEME = CONFIG["theme"]
EVIDENCE = CONFIG["evidence_palette"]
LAYERS = CONFIG["layers"]
BANDS = CONFIG["bands"]

N_PARTICLES = 120
N_NODES = 12


def evidence_color(level):
    return EVIDENCE.get(level, THEME["muted"])


class MeaningIntelligenceScene(Scene):
    """六层演示：界面带 → 加工带 → 元带。"""

    # ------------------------------------------------------------ 基础件
    def setup_scene(self):
        self.camera.background_color = THEME["background"]
        self.timeline = {}
        self.nodes = VGroup()
        self.node_home = []

        self.title = Text(CONFIG["project_name"], font=FONT, font_size=38,
                          color=THEME["text"])
        self.title.to_edge(UP, buff=0.40)
        self.subtitle = Text(f"{CONFIG['project_name_zh']} · 六层应用栈   "
                             f"Six-Layer Application Stack",
                             font=FONT, font_size=19, color=THEME["muted"])
        self.subtitle.next_to(self.title, DOWN, buff=0.14)

        self.caption = Text(LAYERS["L1"]["name"], font=FONT, font_size=27,
                            color=LAYERS["L1"]["color"])
        self.caption.next_to(self.subtitle, DOWN, buff=0.26)

        self.band_group = VGroup(*[
            Text(b["name"], font=FONT, font_size=18, color=THEME["muted"])
            for b in BANDS
        ])
        self.band_group.arrange(DOWN, buff=0.34, aligned_edge=LEFT)
        self.band_group.to_edge(LEFT, buff=0.45).shift(DOWN * 0.25)

    def set_caption(self, key, run_time=0.6):
        layer = LAYERS[key]
        new = Text(layer["name"], font=FONT, font_size=27, color=layer["color"])
        new.next_to(self.subtitle, DOWN, buff=0.26)
        self.play(Transform(self.caption, new), run_time=run_time)

    def highlight_band(self, band_id, run_time=0.5):
        anims = []
        for t, band in zip(self.band_group, BANDS):
            active = band["id"] == band_id
            anims.append(t.animate.set_color(
                THEME["accent"] if active else THEME["muted"]).scale(
                1.12 if active else 1.0 / 1.12))
        self.play(*anims, run_time=run_time)

    def mark(self, name):
        self.timeline[name] = round(self.renderer.time, 2)

    # ------------------------------------------------------------ 主流程
    def construct(self):
        self.setup_scene()

        self.play(Write(self.title), FadeIn(self.subtitle), run_time=1.4)
        self.play(FadeIn(self.caption), FadeIn(self.band_group), run_time=0.7)

        self.act1_reduce_load()
        self.act2_experience()
        self.act3_generate_meaning()
        self.act4_assess_value()
        self.act5_choose_direction()
        self.act6_recursive_reflection()

        self.export_timeline()

    # ------------------------------------------------------------ Act 1
    def act1_reduce_load(self):
        """减负：把 120 个无序粒子收敛为 12 个结构节点。"""
        self.mark("L1_start")
        self.highlight_band("interface")

        rng = np.random.default_rng(20261007)
        noise = VGroup(*[
            Dot(
                point=[rng.uniform(-5.4, 5.4), rng.uniform(-2.2, 1.6), 0],
                radius=0.055,
                color=THEME["accent"],
            ) for _ in range(N_PARTICLES)
        ])

        target_positions = []
        for i in range(N_NODES):
            col, row = i % 4, i // 4
            target_positions.append(np.array([-3.6 + col * 2.4, 0.75 - row * 1.05, 0.0]))

        nodes = VGroup(*[
            Dot(point=pos, radius=0.17, color=LAYERS["L1"]["color"])
            for pos in target_positions
        ])

        self.play(FadeIn(noise, lag_ratio=0.004), run_time=1.1)
        self.wait(0.25)

        # 每个粒子飞向它所属的节点并淡出；节点同时浮现。
        # 粒子与节点是不同的 mobject，不存在同对象动画互相覆盖的问题。
        converge = [
            d.animate.move_to(target_positions[i % N_NODES]).set_opacity(0.0)
            for i, d in enumerate(noise)
        ]
        self.play(*converge, FadeIn(nodes, scale=0.6), run_time=1.9)
        self.remove(noise)

        self.nodes = nodes
        self.node_home = [p.copy() for p in target_positions]

        load_label = Text("120 → 12    负荷从信息量转移到结构",
                          font=FONT, font_size=19, color=THEME["muted"])
        load_label.to_edge(DOWN, buff=0.58)
        self.play(FadeIn(load_label), run_time=0.45)
        self.wait(0.4)
        self.play(FadeOut(load_label), run_time=0.35)

        self.mark("L1_end")

    # ------------------------------------------------------------ Act 2
    def act2_experience(self):
        """可体验：出现可操作控件，节点随参数实时重排。"""
        self.set_caption("L2")
        self.mark("L2_start")

        track = Line(LEFT * 4.2, RIGHT * 4.2, color=THEME["muted"], stroke_width=3)
        track.to_edge(DOWN, buff=1.05)
        knob = Dot(track.get_start(), radius=0.16, color=LAYERS["L2"]["color"])

        readout = Text("spread = 0.45", font=FONT, font_size=18, color=THEME["muted"])
        readout.next_to(track, UP, buff=0.20)

        self.play(Create(track), FadeIn(knob), FadeIn(readout), run_time=0.7)

        baseline = [p.copy() for p in self.node_home]
        state = {"label": readout}

        def spread_updater(mob, dt):
            x0 = track.get_start()[0]
            span = track.get_length() or 1.0
            t = float(np.clip((knob.get_center()[0] - x0) / span, 0.0, 1.0))
            scale = 0.45 + t * 0.9
            for node, home in zip(mob, baseline):
                node.move_to(home * scale)
            new_label = Text(f"spread = {scale:.2f}", font=FONT, font_size=18,
                             color=THEME["muted"])
            new_label.next_to(track, UP, buff=0.20)
            state["label"].become(new_label)

        # 只挂一个组级 updater。挂到 12 个节点上会让共享状态每帧被写 12 次。
        self.nodes.add_updater(spread_updater)

        probe_label = Text("可操作 · 可回放 · 参数改变结果可预测",
                           font=FONT, font_size=19, color=THEME["muted"])
        probe_label.to_edge(DOWN, buff=0.40)
        self.play(FadeIn(probe_label), run_time=0.35)

        self.play(knob.animate.move_to(track.get_end()), run_time=1.7, rate_func=smooth)
        self.play(knob.animate.move_to(track.point_from_proportion(0.55)),
                  run_time=1.1, rate_func=smooth)

        self.nodes.clear_updaters()
        settle = 0.45 + 0.55 * 0.9
        for node, home in zip(self.nodes, baseline):
            node.move_to(home * settle)
        self.node_home = [n.get_center().copy() for n in self.nodes]

        self.play(FadeOut(probe_label), FadeOut(state["label"]), run_time=0.35)
        self.play(FadeOut(track), FadeOut(knob), run_time=0.45)

        self.mark("L2_end")

    # ------------------------------------------------------------ Act 3
    def act3_generate_meaning(self):
        """意义生成：节点归位到 方向·价值·边界 三角。"""
        self.set_caption("L3")
        self.mark("L3_start")

        # 三角整体下移：顶点标签若贴着 y≈1.85，会与上方的层标题（约 y≈2.42）撞在一起。
        top = np.array([0.0, 1.45, 0.0])
        left = np.array([-3.5, -1.25, 0.0])
        right = np.array([3.5, -1.25, 0.0])
        corners = [top, left, right]

        edge_targets = []
        for i in range(N_NODES):
            a, b = corners[i % 3], corners[(i + 1) % 3]
            f = (i // 3 + 1) / 5.0
            edge_targets.append(a * (1 - f) + b * f)

        triangle = Polygon(top, left, right, color=LAYERS["L3"]["color"],
                           stroke_width=3, fill_opacity=0.05)
        vertex_dots = VGroup(*[
            Dot(p, radius=0.13, color=LAYERS["L3"]["color"]) for p in corners
        ])
        labels = VGroup(*[
            Text(txt, font=FONT, font_size=22, color=THEME["text"])
            for txt in ["方向  Direction", "价值  Value", "边界  Boundary"]
        ])
        labels[0].next_to(top, UP, buff=0.20)
        labels[1].next_to(left, DOWN, buff=0.22).shift(LEFT * 0.55)
        labels[2].next_to(right, DOWN, buff=0.22).shift(RIGHT * 0.55)

        moves = [n.animate.move_to(t) for n, t in zip(self.nodes, edge_targets)]
        self.play(Create(triangle), *moves, run_time=2.1)
        self.play(FadeIn(vertex_dots), FadeIn(labels, shift=UP * 0.15), run_time=0.85)

        layer_note = Text("三层次归位：元意义 / 中介意义 / 情境意义",
                          font=FONT, font_size=19, color=THEME["muted"])
        layer_note.to_edge(DOWN, buff=0.40)
        self.play(FadeIn(layer_note), run_time=0.35)
        self.wait(0.5)
        self.play(FadeOut(layer_note), run_time=0.35)

        self.triangle_group = VGroup(triangle, vertex_dots, labels)
        self.mark("L3_end")

    # ------------------------------------------------------------ Act 4
    def act4_assess_value(self):
        """价值评估：为每个节点套上 E0–E6 证据色环，并给出证据色阶。"""
        self.set_caption("L4")
        self.mark("L4_start")

        levels = ["E0", "E1", "E2", "E3", "E4", "E5", "E6"]
        rings = VGroup()
        for i, node in enumerate(self.nodes):
            ring = Circle(radius=0.30, color=evidence_color(levels[i % 7]),
                          stroke_width=3.4)
            ring.move_to(node.get_center())
            rings.add(ring)

        self.play(
            *[Create(r) for r in rings],
            self.triangle_group.animate.set_opacity(0.26),
            run_time=1.5,
        )

        swatches = VGroup()
        for lv in levels:
            box = Square(side_length=0.30, color=evidence_color(lv),
                         fill_opacity=0.85, stroke_width=0)
            txt = Text(lv, font=FONT, font_size=15, color=THEME["text"])
            txt.next_to(box, DOWN, buff=0.10)
            swatches.add(VGroup(box, txt))
        swatches.arrange(RIGHT, buff=0.32).to_edge(DOWN, buff=0.42)

        scale_note = Text("证据等级 E0–E6    每个判断必须写出证伪条件",
                          font=FONT, font_size=19, color=THEME["muted"])
        scale_note.next_to(swatches, UP, buff=0.24)

        self.play(FadeIn(swatches, shift=UP * 0.15), FadeIn(scale_note), run_time=0.85)

        # 证据升级：部分色环换成更高等级。
        # 作用于新建的 ring，与其它动画无对象冲突。
        promoted = [
            r.animate.set_color(evidence_color(levels[(i + 3) % 7])).scale(1.12)
            for i, r in enumerate(rings) if i % 2 == 0
        ]
        self.play(*promoted, run_time=1.3)
        self.wait(0.4)

        self.play(FadeOut(swatches), FadeOut(scale_note), run_time=0.45)
        self.rings = rings
        self.mark("L4_end")

    # ------------------------------------------------------------ Act 5
    def act5_choose_direction(self):
        """方向选择：三条候选路径，两条淡出，一条高亮。"""
        self.set_caption("L5")
        self.mark("L5_start")

        self.play(
            FadeOut(self.rings),
            self.nodes.animate.set_opacity(0.18),
            # 完全隐去三角：留 0.09 的不透明度时，大字标签仍可辨认，会与候选路径互相干扰
            self.triangle_group.animate.set_opacity(0.0),
            run_time=0.65,
        )

        start = np.array([-4.8, -1.45, 0.0])
        ends = [np.array([4.5, 1.70, 0.0]),
                np.array([4.9, 0.05, 0.0]),
                np.array([4.3, -1.75, 0.0])]
        ctrl = [np.array([-0.6, 2.8, 0.0]),
                np.array([0.1, 0.85, 0.0]),
                np.array([-0.4, -2.8, 0.0])]

        paths = VGroup(*[
            CubicBezier(start, c, c, e, color=THEME["muted"], stroke_width=3)
            for c, e in zip(ctrl, ends)
        ])
        tags = VGroup(*[
            Text(t, font=FONT, font_size=18, color=THEME["muted"])
            for t in ["候选 A", "候选 B", "候选 C"]
        ])
        for tag, e in zip(tags, ends):
            tag.next_to(e, RIGHT, buff=0.16)

        self.play(Create(paths), FadeIn(tags), run_time=1.3)
        self.wait(0.35)

        chosen = 1
        fade = [p.animate.set_stroke(width=1.6, opacity=0.30)
                for i, p in enumerate(paths) if i != chosen]
        self.play(
            *fade,
            paths[chosen].animate.set_color(LAYERS["L5"]["color"]).set_stroke(width=6),
            tags[chosen].animate.set_color(LAYERS["L5"]["color"]).scale(1.15),
            *[tags[i].animate.set_opacity(0.30) for i in range(3) if i != chosen],
            run_time=1.4,
        )

        arrow = Arrow(start=paths[chosen].point_from_proportion(0.70),
                      end=ends[chosen], buff=0.05,
                      color=LAYERS["L5"]["color"], stroke_width=6,
                      max_tip_length_to_length_ratio=0.22)
        statement = Text("方向声明 ＋ 预先声明的偏离阈值：一级 <10% ／ 二级 10–30% ／ 三级 >30%",
                         font=FONT, font_size=15, color=THEME["muted"])
        statement.to_edge(DOWN, buff=0.38)

        self.play(GrowArrow(arrow), FadeIn(statement), run_time=0.85)
        self.wait(0.6)
        self.play(FadeOut(statement), run_time=0.35)

        self.paths = paths
        self.arrow = arrow
        self.candidate_tags = tags
        self.mark("L5_end")

    # ------------------------------------------------------------ Act 6
    def act6_recursive_reflection(self):
        """反思与审视递归：螺旋回写至同角度的更高起点 L1'。"""
        self.set_caption("L6")
        self.mark("L6_start")
        self.highlight_band("meta")

        # 螺旋必须完整落在层标题与底部字幕之间。
        # 起点角取 144°：这样 1.6 圈之后（144° + 576° = 720° ≡ 0°）终点正好落在**正右方**，
        # 下一轮起点标记可以向右展开，避让上方标题与下方双行字幕。
        # 若起点角取 -90°（早期写法），终点会落在左上角，标记与层标题重叠。
        center = np.array([0.0, -0.35, 0.0])
        turns = 1.6
        r0, r1 = 1.00, 2.55
        start_angle = PI * 0.8

        def spiral_point(t):
            ang = start_angle + t * turns * TAU
            r = r0 + (r1 - r0) * t
            return center + np.array([r * np.cos(ang), r * np.sin(ang), 0.0])

        # ParametricFunction 以标量 t 调用，必须返回三元组
        def spiral_fn(t):
            p = spiral_point(t)
            return (p[0], p[1], 0.0)

        path = ParametricFunction(spiral_fn, t_range=(0, 1),
                                  color=THEME["fail"], stroke_width=5)
        begin_tag = Text("归零 Zeroing", font=FONT, font_size=18, color=THEME["fail"])
        begin_tag.move_to(center + DOWN * 0.55)

        self.play(FadeOut(self.paths), FadeOut(self.arrow),
                  FadeOut(self.candidate_tags),
                  self.nodes.animate.set_opacity(0.0),
                  self.triangle_group.animate.set_opacity(0.0),
                  run_time=0.65)
        self.play(Create(path), FadeIn(begin_tag), run_time=2.3)

        # 下一轮起点：与原点同角度、半径更大。
        # 归零不是回到原点，而是回到更高一层的起点。
        entry = spiral_point(1.0)
        entry_shifted = center + (entry - center) * 1.13

        marker = Circle(radius=0.26, color=THEME["fail"], stroke_width=5)
        marker.move_to(entry_shifted)
        next_tag = Text("L1′  下一轮起点  Next-cycle entry",
                        font=FONT, font_size=17, color=THEME["fail"])
        next_tag.next_to(marker, RIGHT, buff=0.26)

        self.play(FadeIn(marker, scale=0.5), FadeIn(next_tag), run_time=0.75)

        finale = Text("归零不是回到原点，而是回到更高一层的起点",
                      font=FONT, font_size=22, color=THEME["text"])
        finale.to_edge(DOWN, buff=0.72)
        finale_en = Text("Zeroing returns not to the origin, but to a higher entry point",
                         font=FONT, font_size=15, color=THEME["muted"])
        finale_en.next_to(finale, DOWN, buff=0.12)

        self.play(Write(finale), FadeIn(finale_en), run_time=1.2)

        # 回环扫描：三带依次点亮，表示 L6 改写前五层的前提
        for band in BANDS:
            self.highlight_band(band["id"], run_time=0.32)

        self.wait(0.9)
        self.mark("L6_end")

    # ------------------------------------------------------------ 导出
    def export_timeline(self):
        output = {}
        for key in LAYER_ORDER:
            layer = LAYERS[key]
            output[key] = {
                "name": f"{layer['name']} ({layer['en']})",
                "index": layer["index"],
                "band": layer["band"],
                "start": self.timeline.get(f"{key}_start", 0.0),
                "end": self.timeline.get(f"{key}_end", 0.0),
            }
        out_path = BASE_DIR / "timeline.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        safe_print(f"[timeline] 已导出六层实测时间轴：{out_path}")
