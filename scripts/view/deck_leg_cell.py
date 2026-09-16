"""The leg cell talk as animated scenes, one mechanism per scene.

Built to be narrated live, so each scene shows a thing happening and the screen carries only the
words that a picture cannot. Every figure on screen comes from `plan/leg-cell-plan.html` and the
experiment records of 2026-09-15 and 2026-09-16.

The palette and the typeface are the report's, so the talk and the page read as one document.
Manim runs in its own environment: its Pango stack and the simulator's do not share a libffi.

    env -u PYTHONPATH /home/flux/miniconda3/envs/manim/bin/manim -qh \
        --media_dir ~/Videos/meat-cell/deck \
        scripts/view/deck_leg_cell.py Title Problem Fixture Contract Turn Numbers Transfer Assumption

There is no LaTeX on this machine, so every label is Pango text and no scene may use `Tex`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from manim import (
    DEGREES,
    DOWN,
    LEFT,
    RIGHT,
    UP,
    AnimationGroup,
    Arrow,
    Circle,
    Create,
    DashedLine,
    Dot,
    FadeIn,
    FadeOut,
    Flash,
    Indicate,
    LaggedStart,
    Line,
    Polygon,
    Rectangle,
    ReplacementTransform,
    Scene,
    SVGMobject,
    Text,
    Transform,
    UpdateFromAlphaFunc,
    VGroup,
    VMobject,
    Write,
    config,
    rate_functions,
)

# The report's dark theme. Dark because the talk is projected in a lit room.
PAPER = "#161616"
INK = "#E5E4E0"
INK_2 = "#B3B2AC"
INK_3 = "#84837D"
RULE = "#5D5C58"
BLUE = "#8FB0EC"
BLUE_SOFT = "#1C2740"
BELT = "#2C2C2A"
MEAT = "#C89A92"
WARN = "#D98A6A"

FONT = "B612"
MONO = "B612 Mono"

# One type scale, four steps, used everywhere.
DISPLAY, HEAD, BODY, ANNOT = 42, 30, 24, 20

config.background_color = PAPER

# One belt across the frame, the saw at the right, the arm working to its left.
BELT_LEFT, BELT_RIGHT = -7.4, 7.4
BELT_TOP, BELT_BOTTOM = 2.15, -2.15
BLADE_X = 4.6

EASE = rate_functions.ease_out_expo


def line(text: str, size: int = BODY, color: str = INK, weight: str = "NORMAL") -> Text:
    """A line of prose in the report's text face."""
    return Text(text, font=FONT, font_size=size, color=color, weight=weight)


def figure(text: str, size: int = BODY, color: str = INK) -> Text:
    """A measured value or a code name, in the report's mono face."""
    return Text(text, font=MONO, font_size=size, color=color)


def annot(text: str, color: str = INK_3) -> Text:
    """A label on a drawn object, the way the report labels a figure."""
    return Text(text, font=MONO, font_size=ANNOT, color=color)


def leader(anchor: np.ndarray, label: Text, colour: str = RULE) -> VGroup:
    """A leader from `label` to `anchor`: straight when they share a column, elbowed otherwise."""
    end = label.get_top() if label.get_center()[1] < anchor[1] else label.get_bottom()
    end = end + (UP if label.get_center()[1] < anchor[1] else DOWN) * 0.12
    if abs(end[0] - anchor[0]) < 0.25:
        path = Line([anchor[0], end[1], 0], anchor, color=colour, stroke_width=1.6)
    else:
        knee = np.array([anchor[0], end[1] + np.sign(anchor[1] - end[1]) * 0.45, 0.0])
        path = VMobject(color=colour, stroke_width=1.6, fill_opacity=0)
        path.set_points_as_corners([end, np.array([end[0], knee[1], 0.0]), knee, anchor])
    return VGroup(path, Dot(anchor, radius=0.035, color=colour))


def belt() -> VGroup:
    """The conveyor: a surface between two edges."""
    surface = Rectangle(
        width=BELT_RIGHT - BELT_LEFT,
        height=BELT_TOP - BELT_BOTTOM,
        fill_color=BELT,
        fill_opacity=1,
        stroke_width=0,
    ).move_to([(BELT_LEFT + BELT_RIGHT) / 2, 0, 0])
    far = Line([BELT_LEFT, BELT_TOP, 0], [BELT_RIGHT, BELT_TOP, 0], color=RULE, stroke_width=2)
    near = Line([BELT_LEFT, BELT_BOTTOM, 0], [BELT_RIGHT, BELT_BOTTOM, 0], color=RULE, stroke_width=2)
    return VGroup(surface, far, near)


def belt_speed() -> VGroup:
    """The belt's direction and speed, stated once rather than mimed."""
    shaft = Arrow(
        [BELT_LEFT + 0.6, BELT_BOTTOM - 0.75, 0],
        [BELT_LEFT + 2.4, BELT_BOTTOM - 0.75, 0],
        buff=0,
        color=INK_3,
        stroke_width=3,
        max_tip_length_to_length_ratio=0.18,
    )
    return VGroup(shaft, annot("0.30 m/s").next_to(shaft, RIGHT, buff=0.25))


def blade_plane() -> VGroup:
    """The plane the saw cuts in, which is what every result is measured against."""
    plane = Line([BLADE_X, BELT_TOP + 0.4, 0], [BLADE_X, BELT_BOTTOM - 0.4, 0], color=BLUE, stroke_width=3)
    return VGroup(plane, annot("blade plane", BLUE).next_to(plane, DOWN, buff=0.16))


# The simulated leg's own cross sections, from LEG_PROFILE in sim/product.py:
# the fraction along the leg and the half width there, in metres, on the 722 mm
# default leg. Drawing from this table keeps the talk and the simulator honest
# about the same shape.
LEG_LENGTH_M = 0.722
LEG_SECTIONS = (
    (0.00, 0.085),
    (0.10, 0.120),
    (0.28, 0.125),
    (0.45, 0.092),
    (0.55, 0.058),
    (0.70, 0.048),
    (0.85, 0.040),
    (0.93, 0.038),
    (1.00, 0.012),
)
# Where the centre of gravity sits along the leg: the volume centroid of LEG_PROFILE's
# elliptical sections, integrated (0.324). The hock fraction is HOCK_FRACTION in product.py.
COG_FRACTION = 0.32
HOCK_FRACTION = 0.76
GRASP_FRACTION = 0.70


def leg_point(length: float, fraction: float, side: float = 0.0) -> np.ndarray:
    """A point on the leg drawn `length` units long, measured from its centre of gravity.

    `fraction` runs 0 at the ham's cut face to 1 at the trotter's tip. `side` of
    +1 or -1 puts the point on the outline, 0 on the axis.
    """
    x = (fraction - COG_FRACTION) * length
    half = np.interp(fraction, [f for f, _ in LEG_SECTIONS], [w for _, w in LEG_SECTIONS])
    return np.array([x, side * half / LEG_LENGTH_M * length, 0.0])


def leg(length: float = 2.2) -> VGroup:
    """A leg seen from above, drawn from the simulator's cross sections.

    Laid along +x with the ham's cut face at the left. The group's centre is the
    centre of gravity, so rotating the group about its own centre is the turn the
    cell performs. `hock_offset` is the distance from that centre to the joint the
    saw cuts.
    """
    upper = [leg_point(length, f, 1.0) for f, _ in LEG_SECTIONS]
    lower = [leg_point(length, f, -1.0) for f, _ in reversed(LEG_SECTIONS)]
    body = VMobject(fill_color=MEAT, fill_opacity=1, stroke_width=0)
    body.set_points_smoothly([*upper, *lower, upper[0]])
    group = VGroup(body)
    group.length = length
    group.hock_offset = (HOCK_FRACTION - COG_FRACTION) * length
    return group


def jaws(opening: float, height: float = 1.0, color: str = BLUE) -> VGroup:
    """A two-jaw gripper seen from above, open by `opening` in frame units."""
    pad = Rectangle(width=0.16, height=height, fill_color=color, fill_opacity=1, stroke_width=0)
    left, right = pad.copy(), pad.copy()
    left.shift(LEFT * opening / 2)
    right.shift(RIGHT * opening / 2)
    return VGroup(left, right)


def jaws_close(grip: VGroup) -> AnimationGroup:
    """Close a pair of jaws onto what sits between them."""
    centre = (grip[0].get_center() + grip[1].get_center()) / 2
    left = grip[0].animate.move_to(centre + (grip[0].get_center() - centre) * 0.45)
    right = grip[1].animate.move_to(centre + (grip[1].get_center() - centre) * 0.45)
    return AnimationGroup(left, right)


def six_axis(height: float = 2.6) -> VGroup:
    """A six-axis arm in side view, schematic: base, shoulder, elbow, wrist, tool."""
    unit = height / 2.6
    base = Rectangle(width=0.9 * unit, height=0.3 * unit, fill_color=INK_2, fill_opacity=1, stroke_width=0)
    base.move_to([0, -1.15 * unit, 0])
    joints = [
        np.array([0.0, -1.0 * unit, 0.0]),
        np.array([0.0, 0.15 * unit, 0.0]),
        np.array([1.15 * unit, 0.75 * unit, 0.0]),
        np.array([1.95 * unit, 0.15 * unit, 0.0]),
    ]
    links = VGroup(*[Line(joints[i], joints[i + 1], color=INK_2, stroke_width=10) for i in range(len(joints) - 1)])
    pivots = VGroup(*[Dot(j, radius=0.12 * unit, color=PAPER) for j in joints[:-1]])
    tool = Line(joints[-1], joints[-1] + DOWN * 0.45 * unit, color=BLUE, stroke_width=10)
    return VGroup(base, links, pivots, tool)


def scara(height: float = 2.6) -> VGroup:
    """A SCARA in side view, schematic: column, two links in one plane, a vertical spindle."""
    unit = height / 2.6
    base = Rectangle(width=0.9 * unit, height=0.3 * unit, fill_color=INK_2, fill_opacity=1, stroke_width=0)
    base.move_to([0, -1.15 * unit, 0])
    column = Line([0, -1.0 * unit, 0], [0, 0.75 * unit, 0], color=INK_2, stroke_width=10)
    upper = Line([0, 0.75 * unit, 0], [1.15 * unit, 0.75 * unit, 0], color=INK_2, stroke_width=10)
    fore = Line([1.15 * unit, 0.75 * unit, 0], [1.95 * unit, 0.75 * unit, 0], color=INK_2, stroke_width=10)
    spindle = Line([1.95 * unit, 0.75 * unit, 0], [1.95 * unit, 0.05 * unit, 0], color=INK_2, stroke_width=5)
    tool = Line([1.95 * unit, 0.05 * unit, 0], [1.95 * unit, -0.4 * unit, 0], color=BLUE, stroke_width=7)
    pivots = VGroup(
        Dot([0, 0.75 * unit, 0], radius=0.12 * unit, color=PAPER),
        Dot([1.15 * unit, 0.75 * unit, 0], radius=0.12 * unit, color=PAPER),
    )
    return VGroup(base, column, upper, fore, spindle, pivots, tool)


class Title(Scene):
    """Who this is and what it is about."""

    def construct(self) -> None:
        """Hold one title while a leg crosses behind it."""
        self.add(belt())
        piece = leg().rotate(28 * DEGREES).move_to([BELT_LEFT - 1.0, -1.15, 0])
        self.add(piece)

        name = line("Aligning pork legs to the trotter saw", size=DISPLAY).shift(UP * 0.55)
        who = line("Synphony Robotics, for Prestage Foods of Iowa", size=BODY, color=INK_2)
        who.next_to(name, DOWN, buff=0.45)
        self.play(
            piece.animate.shift(RIGHT * 9.0).set_rate_func(rate_functions.linear),
            LaggedStart(Write(name), FadeIn(who, shift=UP * 0.2), lag_ratio=0.45),
            run_time=4.0,
        )
        self.wait(1.4)


class Pig(Scene):
    """Where the piece comes from, and which piece this is."""

    def construct(self) -> None:
        """One side of a hog, its primals, and the one this cell handles."""
        pig = SVGMobject(str(Path(__file__).resolve().parent / "assets" / "pig-side.svg"))
        pig.set_height(4.2).move_to([0, -0.45, 0])
        leg_region, outline, ear, tail, *cuts = pig
        outline.set_stroke(INK, width=2.5).set_fill(opacity=0)
        ear.set_stroke(INK, width=2).set_fill(opacity=0)
        tail.set_stroke(INK, width=2).set_fill(opacity=0)
        leg_region.set_fill(PAPER, opacity=0).set_stroke(width=0)
        for cut in cuts:
            cut.set_stroke(RULE, width=2).set_fill(opacity=0)

        heading = line("A hog is split into sides, and a side into primals.", size=HEAD)
        heading.to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.1)
        self.play(Create(outline, rate_func=EASE), Create(ear), Create(tail), run_time=2.0)
        self.wait(0.5)
        self.play(LaggedStart(*[Create(cut) for cut in cuts], lag_ratio=0.25), run_time=1.6)

        # Labels sit at fractions of the drawing, so they follow it if it moves.
        left, right = pig.get_left()[0], pig.get_right()[0]
        bottom, top = pig.get_bottom()[1], pig.get_top()[1]

        def at(fx: float, fy: float) -> np.ndarray:
            return np.array([left + fx * (right - left), bottom + fy * (top - bottom), 0.0])

        names = VGroup(
            line("shoulder", size=ANNOT, color=INK_2).move_to(at(0.22, 0.42)),
            line("loin", size=ANNOT, color=INK_2).move_to(at(0.50, 0.70)),
            line("belly", size=ANNOT, color=INK_2).move_to(at(0.50, 0.32)),
            line("leg", size=ANNOT, color=INK_2).move_to(at(0.86, 0.08)),
        )
        self.play(LaggedStart(*[FadeIn(n) for n in names], lag_ratio=0.2), run_time=1.6)
        self.wait(1.0)

        each = line("Each primal goes down its own line.", size=BODY, color=INK_2)
        each.next_to(heading, DOWN, buff=0.3)
        self.play(FadeIn(each), run_time=0.9)
        self.wait(1.4)

        # The one this cell handles.
        self.play(
            leg_region.animate.set_fill(MEAT, opacity=1),
            names[3].animate.set_color(MEAT).scale(1.15),
            *[n.animate.set_opacity(0.35) for n in names[:3]],
            FadeOut(each),
            run_time=1.2,
        )
        ours = line("This cell works on the leg, sold as ham.", size=BODY, color=BLUE)
        ours.next_to(heading, DOWN, buff=0.3)
        self.play(FadeIn(ours), run_time=1.0)
        self.wait(1.2)

        still = line("It arrives with the foot still on.", size=BODY, color=INK_2).move_to(ours.get_center())
        self.play(ReplacementTransform(ours, still), run_time=0.9)
        self.wait(1.8)


class Anatomy(Scene):
    """The leg itself: its parts, its axis, and where the foot comes off."""

    def construct(self) -> None:
        """Name the parts, draw the axis, and mark the joint the saw cuts."""
        length = 9.4
        piece = leg(length).move_to([0, 0.55, 0])
        # The bounding box is centred at half the length; the centre of gravity is short of that.
        base = piece.get_center() + RIGHT * (COG_FRACTION - 0.5) * length
        self.play(FadeIn(piece), run_time=0.9)
        heading = line("One leg: 722 mm, 11 kg, the shape the simulator uses.", size=HEAD)
        heading.to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        # Labels live in three fixed bands, so no two can collide.
        name_band, deep_band, top_band = -1.75, -2.75, 2.5

        def tag(fraction: float, text: str, colour: str = INK_2) -> VGroup:
            edge = leg_point(length, fraction, -1.0) + base
            label = annot(text, colour).move_to([edge[0], name_band, 0])
            return VGroup(leader(edge, label), label)

        parts = VGroup(
            tag(0.03, "ham butt"),
            tag(0.28, "ham"),
            tag(0.70, "shank"),
            tag(0.95, "trotter"),
        )
        for part in parts:
            self.play(Create(part[0]), FadeIn(part[1]), run_time=0.5)
        self.wait(1.0)

        axis = DashedLine(
            leg_point(length, 0.0) + base,
            leg_point(length, 1.0) + base,
            color=INK_3,
            stroke_width=2,
            dash_length=0.12,
        )
        axis_name = annot("the leg's axis").move_to([leg_point(length, 0.12)[0] + base[0], deep_band, 0])
        axis_lead = leader(leg_point(length, 0.12) + base, axis_name)
        self.play(Create(axis, rate_func=EASE), FadeIn(axis_name), Create(axis_lead), run_time=1.3)

        cog = Dot(base, radius=0.09, color=BLUE)
        cog_name = annot("centre of gravity", BLUE).move_to([base[0] + 2.7, deep_band, 0])
        cog_stem = leader(base, cog_name, BLUE)
        self.play(FadeIn(cog), Create(cog_stem), FadeIn(cog_name), run_time=1.0)
        self.wait(1.2)

        hock_x = (leg_point(length, HOCK_FRACTION) + base)[0]
        hock = Dot([hock_x, base[1], 0], radius=0.09, color=WARN)
        hock_line = Line([hock_x, base[1] + 1.0, 0], [hock_x, base[1] - 0.9, 0], color=WARN, stroke_width=3)
        hock_name = annot("the hock joint, 76 percent along", WARN).move_to([hock_x - 1.4, top_band, 0])
        hock_stem = leader(np.array([hock_x, base[1] + 1.0, 0.0]), hock_name, WARN)
        self.play(Create(hock_line), FadeIn(hock), Create(hock_stem), FadeIn(hock_name), run_time=1.2)
        self.wait(1.0)

        job = line("The saw takes the foot off at or just above that joint.", size=BODY, color=WARN)
        job.move_to([0, deep_band - 0.7, 0])
        self.play(FadeIn(job), run_time=1.0)
        self.wait(2.2)


class Handle(Scene):
    """Where a gripper can hold a leg, measured against what the jaws open to."""

    def construct(self) -> None:
        """Lay each station's width beside the jaw opening and see which fits."""
        length = 8.6
        piece = leg(length).move_to([0, 0.95, 0])
        # The bounding box is centred at half the length; the centre of gravity is short of that.
        base = piece.get_center() + RIGHT * (COG_FRACTION - 0.5) * length
        self.add(piece)
        heading = line("Where the jaws can hold a leg.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        # One bar for what the jaws open to, to compare every station against.
        per_metre = length / LEG_LENGTH_M
        opening = 0.180 * per_metre
        gauge = Line([-5.4, -2.5, 0], [-5.4 + opening, -2.5, 0], color=BLUE, stroke_width=6)
        gauge_name = figure("the jaws open 180 mm", size=ANNOT, color=BLUE)
        gauge_name.next_to(gauge, DOWN, buff=0.28).align_to(gauge, LEFT)
        self.play(Create(gauge, rate_func=EASE), FadeIn(gauge_name), run_time=1.1)
        self.wait(0.6)

        stations = (
            (0.28, "the ham is 250 mm across", "wider than the jaws open", WARN),
            (0.95, "the trotter is 61 mm across", "thin, and it swings on the joint", WARN),
            (GRASP_FRACTION, "the shank is 96 mm across", "bone under the skin, and it fits", BLUE),
        )
        for fraction, what, why, colour in stations:
            top = leg_point(length, fraction, 1.0) + base
            bottom = leg_point(length, fraction, -1.0) + base
            span = Line(top, bottom, color=colour, stroke_width=5)
            what_name = annot(what, colour).move_to([top[0], 2.65, 0])
            if what_name.get_right()[0] > 6.8:
                what_name.shift(LEFT * (what_name.get_right()[0] - 6.8))
            self.play(Create(span), FadeIn(what_name), run_time=0.7)

            # Lay that width flat beside the gauge, so the comparison is one look.
            laid = Line([-5.4, -1.7, 0], [-5.4 + span.get_length(), -1.7, 0], color=colour, stroke_width=6)
            why_name = annot(why, colour).next_to(laid, RIGHT, buff=0.35)
            self.play(ReplacementTransform(span.copy(), laid), run_time=0.9)
            self.play(FadeIn(why_name), run_time=0.6)
            self.wait(1.3)

            if colour is BLUE:
                grip = jaws(opening, height=1.6).rotate(90 * DEGREES)
                grip.move_to([top[0], (top[1] + bottom[1]) / 2, 0])
                self.play(FadeIn(grip), run_time=0.5)
                self.play(jaws_close(grip), run_time=0.6)
                self.wait(1.2)
            else:
                self.play(FadeOut(span), FadeOut(what_name), FadeOut(laid), FadeOut(why_name), run_time=0.5)

        held = line("So the cell holds the shank, seven tenths along.", size=BODY, color=BLUE)
        held.move_to([6.8, -3.45, 0], aligned_edge=RIGHT)
        self.play(FadeIn(held), run_time=1.0)
        self.wait(2.2)


class WhySkills(Scene):
    """A crossbar would square a leg. What the arm is for is everything after that."""

    def construct(self) -> None:
        """Show the fixture that solves this job, then what it cannot be carried to."""
        self.add(belt())
        bar = Line([0.2, BELT_TOP + 0.15, 0], [3.1, BELT_BOTTOM - 0.15, 0], color=BLUE, stroke_width=7)
        heading = line("A crossbar could square these.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(Create(bar, rate_func=EASE), FadeIn(heading, shift=DOWN * 0.15), run_time=1.2)

        skewed = VGroup(*[leg(1.9).rotate(y * DEGREES) for y in (-30, 18, -14)])
        for index, piece in enumerate(skewed):
            piece.move_to([BELT_LEFT - 0.8 - 3.0 * index, 0.7 - 0.55 * index, 0])
        self.add(skewed)
        self.play(skewed.animate.shift(RIGHT * 4.6).set_rate_func(rate_functions.linear), run_time=2.0)
        squared = VGroup(*[leg(1.9).move_to([piece.get_center()[0] + 0.6, 0.0, 0]) for piece in skewed])
        self.play(Transform(skewed, squared, rate_func=EASE), run_time=1.2)
        self.play(skewed.animate.shift(RIGHT * 4.4).set_rate_func(rate_functions.linear), run_time=1.9)
        aside = line("It needs no camera and no teaching.", size=BODY, color=INK_2)
        aside.next_to(heading, DOWN, buff=0.28)
        self.play(FadeIn(aside), run_time=0.8)
        self.wait(1.6)
        self.play(*[FadeOut(m) for m in (skewed, bar, aside, heading)], run_time=0.8)
        self.clear()

        # What the arm is actually for.
        mission = line("Squaring a leg is one job.", size=HEAD).shift(UP * 0.9)
        rest = VGroup(
            line("I am building a physical system that learns a job", size=HEAD),
            line("and carries what it learned to the next one.", size=HEAD),
        ).arrange(DOWN, buff=0.28)
        rest.next_to(mission, DOWN, buff=0.55)
        self.play(Write(mission), run_time=1.3)
        self.play(LaggedStart(*[Write(x) for x in rest], lag_ratio=0.5), run_time=2.2)
        self.wait(1.8)
        self.play(FadeOut(mission), FadeOut(rest), run_time=0.8)

        # Aligning a piece is one skill, and the skill is not the machine.
        skill = Rectangle(width=5.6, height=1.15, color=BLUE, stroke_width=3).shift(UP * 2.3)
        skill_name = figure("align a piece on a belt", size=BODY, color=BLUE).move_to(skill.get_center())
        self.play(Create(skill, rate_func=EASE), FadeIn(skill_name), run_time=1.1)

        arms = VGroup(six_axis(3.4), scara(3.4)).arrange(RIGHT, buff=3.0, aligned_edge=DOWN)
        arms.move_to([0, -0.95, 0])
        names = VGroup(
            line("six-axis", size=ANNOT, color=INK_2).next_to(arms[0], DOWN, buff=0.22),
            line("SCARA", size=ANNOT, color=INK_2).next_to(arms[1], DOWN, buff=0.22),
        )
        self.play(LaggedStart(FadeIn(arms[0]), FadeIn(arms[1]), lag_ratio=0.35), FadeIn(names), run_time=1.6)

        drops = VGroup(
            *[
                Arrow(
                    skill.get_bottom(),
                    arm.get_top() + UP * 0.15,
                    buff=0.12,
                    color=BLUE,
                    stroke_width=3,
                    max_tip_length_to_length_ratio=0.16,
                )
                for arm in arms
            ]
        )
        self.play(LaggedStart(*[Create(d) for d in drops], lag_ratio=0.3), run_time=1.4)
        same = line("The same skill, written once, run on either.", size=BODY, color=BLUE)
        same.move_to([0, -3.5, 0])
        self.play(FadeIn(same), run_time=1.0)
        self.wait(2.2)


class Definition(Scene):
    """What the word skill means here, part by part."""

    def construct(self) -> None:
        """Build the five slots of a contract, then show the implementation is free to change."""
        heading = line("What I mean by a skill.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        outer = Rectangle(width=12.8, height=4.7, color=BLUE, stroke_width=3).move_to([0, -0.1, 0])
        title = figure("close the jaws on the shank", size=BODY, color=BLUE)
        title.move_to(outer.get_top() + DOWN * 0.45)
        self.play(Create(outer, rate_func=EASE), FadeIn(title), run_time=1.2)

        slots = (
            ("what it needs", "the chosen grasp on the moving shank"),
            ("what must be true first", "the jaws open 40 mm wider than the shank"),
            ("what it does", "a rule, a planner, or a trained model"),
            ("what it gives back", "the opening it closed to, and the lift"),
            ("how it knows it worked", "the piece rose with the tool, within 2 mm"),
        )
        rows = VGroup()
        for index, (name, meaning) in enumerate(slots):
            y = 1.3 - index * 0.72
            left = figure(name, size=ANNOT, color=INK).move_to([-6.0, y, 0], aligned_edge=LEFT)
            right = line(meaning, size=ANNOT, color=INK_2).move_to([-0.7, y, 0], aligned_edge=LEFT)
            rows.add(VGroup(left, right))
        for row in rows:
            self.play(FadeIn(row, shift=RIGHT * 0.18), run_time=0.55)
        self.wait(1.6)

        self.play(Indicate(rows[4][0], color=BLUE, scale_factor=1.08), run_time=0.9)
        test = line("The success test is what separates a skill from a function.", size=BODY, color=BLUE)
        test.move_to([0, -3.15, 0])
        self.play(FadeIn(test), run_time=1.1)
        self.wait(2.0)
        self.play(FadeOut(test), FadeOut(rows), FadeOut(title), run_time=0.7)

        swap = (
            VGroup(
                figure("a rule", size=BODY, color=INK),
                figure("a planner", size=BODY, color=INK),
                figure("a trained model", size=BODY, color=INK),
            )
            .arrange(RIGHT, buff=1.5)
            .move_to(outer.get_center())
        )
        same = (
            VGroup(
                line("Any of these can sit inside. The contract does not change,", size=BODY, color=INK_2),
                line("so nothing downstream has to be rewritten.", size=BODY, color=INK_2),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -3.25, 0])
        )
        self.play(LaggedStart(*[FadeIn(x, scale=1.1) for x in swap], lag_ratio=0.3), run_time=1.5)
        self.play(FadeIn(same), run_time=1.0)
        self.wait(2.2)


class Fuse(Scene):
    """The three drills fused into play, and what makes a learned skill carry to new ground."""

    def construct(self) -> None:
        """Fuse the drills, then show one skill carried across conditions, ending on our own evidence."""
        drills = ("first touch", "close control", "carrying at speed")
        boxes = VGroup()
        for text in drills:
            frame = Rectangle(width=3.6, height=1.0, color=RULE, stroke_width=2)
            boxes.add(VGroup(frame, figure(text, size=ANNOT, color=INK).move_to(frame.get_center())))
        boxes.arrange(RIGHT, buff=0.55).move_to([0, 2.2, 0])
        heading = line("In a match all three run at once.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)
        self.play(LaggedStart(*[FadeIn(b, shift=DOWN * 0.2) for b in boxes], lag_ratio=0.2), run_time=1.3)
        self.wait(0.6)

        fused = Rectangle(width=8.2, height=1.2, color=BLUE, stroke_width=3).move_to([0, -0.4, 0])
        fused_name = figure("take the ball past a defender at speed", size=ANNOT, color=BLUE)
        fused_name.move_to(fused.get_center())
        feeds = VGroup(
            *[
                Arrow(
                    b.get_bottom(),
                    fused.get_top(),
                    buff=0.12,
                    color=INK_3,
                    stroke_width=3,
                    max_tip_length_to_length_ratio=0.12,
                )
                for b in boxes
            ]
        )
        self.play(LaggedStart(*[Create(f) for f in feeds], lag_ratio=0.15), run_time=1.2)
        self.play(Create(fused, rate_func=EASE), FadeIn(fused_name), run_time=1.1)
        taught = line("A skill of its own, made from the three during play.", size=BODY, color=INK_2)
        taught.move_to([0, -1.9, 0])
        self.play(FadeIn(taught), run_time=1.0)
        self.wait(1.6)

        works = (
            VGroup(
                line("It works because each drill has its own standard of done,", size=ANNOT, color=INK_2),
                line("and all three read and change the same things: the ball and the body.", size=ANNOT, color=INK_2),
            )
            .arrange(DOWN, buff=0.16)
            .move_to([0, -3.1, 0])
        )
        self.play(FadeIn(works), run_time=1.1)
        self.wait(2.2)
        self.play(*[FadeOut(m) for m in (boxes, feeds, fused, fused_name, taught, works, heading)], run_time=0.8)

        # A skill learned over variation carries to conditions it was not drilled on.
        carry = line("Learned over enough variation, a skill carries.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(carry, shift=DOWN * 0.15), run_time=1.0)
        core = Rectangle(width=4.0, height=1.1, color=BLUE, stroke_width=3).move_to([0, 0.2, 0])
        core_name = figure("close control", size=BODY, color=BLUE).move_to(core.get_center())
        self.play(Create(core, rate_func=EASE), FadeIn(core_name), run_time=1.0)
        contexts = (
            ("wet grass", [-4.6, 1.9, 0]),
            ("a new ball", [4.6, 1.9, 0]),
            ("a faster game", [-4.6, -1.5, 0]),
            ("a different pitch", [4.6, -1.5, 0]),
        )
        spokes = VGroup()
        for text, at in contexts:
            tag = line(text, size=ANNOT, color=INK_2).move_to(at)
            # From the box corner facing the tag to the tag's facing edge, so no spoke crosses the box.
            corner = np.array(
                [
                    core.get_right()[0] if at[0] > 0 else core.get_left()[0],
                    core.get_top()[1] if at[1] > 0 else core.get_bottom()[1],
                    0.0,
                ]
            )
            end = tag.get_bottom() if at[1] > 0 else tag.get_top()
            spoke = Line(corner, end + (DOWN if at[1] > 0 else UP) * 0.12, color=RULE, stroke_width=1.6)
            spokes.add(VGroup(spoke, tag))
        self.play(LaggedStart(*[FadeIn(sp) for sp in spokes], lag_ratio=0.2), run_time=1.6)
        self.wait(1.4)

        # The same claim, on this cell's own measurements.
        ours = (
            ("legs it never saw", "centre of gravity 1.2 mm median, on 20 held-out legs"),
            ("a different arm", "one turn skill on the UR20 and the SR-20iA"),
            ("a different piece", "the same skills on a loin, 20 of 20 near square"),
        )
        swapped = VGroup()
        for index, (label_text, _) in enumerate(ours):
            swapped.add(line(label_text, size=ANNOT, color=BLUE).move_to(contexts[index][1]))
        self.play(
            ReplacementTransform(
                core_name, figure("the cell's skills", size=BODY, color=BLUE).move_to(core.get_center())
            ),
            *[ReplacementTransform(spokes[i][1], swapped[i]) for i in range(3)],
            FadeOut(spokes[3]),
            run_time=1.3,
        )
        evidence = VGroup(*[figure(proof, size=ANNOT, color=INK) for _, proof in ours]).arrange(DOWN, buff=0.22)
        evidence.move_to([0, -2.6, 0])
        self.play(LaggedStart(*[FadeIn(e) for e in evidence], lag_ratio=0.3), run_time=1.6)
        self.wait(2.6)


class Compose(Scene):
    """Four skills make the one that aligns a leg, and a skill can be any size that tests itself."""

    def construct(self) -> None:
        """The cell's own composition, then the ladder of sizes."""
        heading = line("Four skills align one leg.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        parts = ["perceive the piece", "find where to hold it", "hold it", "turn it"]
        boxes = VGroup()
        for text in parts:
            frame = Rectangle(width=4.4, height=0.85, color=RULE, stroke_width=2)
            boxes.add(VGroup(frame, figure(text, size=ANNOT, color=INK_2).move_to(frame.get_center())))
        boxes.arrange(DOWN, buff=0.28).move_to([-3.2, -0.25, 0])
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * 0.2) for b in boxes], lag_ratio=0.15), run_time=1.5)

        composed = Rectangle(width=5.0, height=1.25, color=BLUE, stroke_width=3).move_to([3.7, -0.25, 0])
        composed_name = figure("align a leg for the saw", size=BODY, color=BLUE).move_to(composed.get_center())
        self.play(Create(composed, rate_func=EASE), FadeIn(composed_name), run_time=1.0)
        joins = VGroup(
            *[
                Arrow(
                    b.get_right(),
                    composed.get_left(),
                    buff=0.18,
                    color=INK_3,
                    stroke_width=2.5,
                    max_tip_length_to_length_ratio=0.08,
                )
                for b in boxes
            ]
        )
        self.play(LaggedStart(*[Create(j) for j in joins], lag_ratio=0.15), run_time=1.3)
        self.wait(1.6)
        self.play(*[FadeOut(m) for m in (boxes, joins, composed, composed_name, heading)], run_time=0.8)

        ladder_heading = line("How big a skill can be.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(ladder_heading, shift=DOWN * 0.15), run_time=0.9)
        rungs = [
            ("move one joint", False),
            ("close the jaws on the shank", True),
            ("align a leg for the saw", True),
            ("run the leg station", True),
            ("run the plant", True),
        ]
        ladder = VGroup()
        for text, is_skill in rungs:
            frame = Rectangle(width=7.0, height=0.8, color=BLUE if is_skill else RULE, stroke_width=2)
            ladder.add(
                VGroup(frame, figure(text, size=ANNOT, color=INK if is_skill else INK_3).move_to(frame.get_center()))
            )
        ladder.arrange(DOWN, buff=0.2).move_to([-1.5, 0.15, 0])
        command = line("a command, no test of its own", size=ANNOT, color=INK_3)
        command.next_to(ladder[0], RIGHT, buff=0.3)
        self.play(LaggedStart(*[FadeIn(r, shift=UP * 0.15) for r in ladder], lag_ratio=0.15), run_time=1.8)
        self.play(FadeIn(command), run_time=0.7)
        self.wait(1.0)
        answer = (
            VGroup(
                line("Any size that states what it needs", size=BODY, color=BLUE),
                line("and tests whether it worked.", size=BODY, color=BLUE),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -3.1, 0])
        )
        self.play(FadeIn(answer), run_time=1.1)
        self.wait(2.2)


def chain(names: tuple[str, ...], width: float = 2.25, buff: float = 0.45) -> tuple[VGroup, VGroup]:
    """A row of named boxes and the arrows between them."""
    boxes = VGroup()
    for text in names:
        frame = Rectangle(width=width, height=0.88, color=RULE, stroke_width=2)
        boxes.add(VGroup(frame, figure(text, size=ANNOT, color=INK).move_to(frame.get_center())))
    boxes.arrange(RIGHT, buff=buff)
    links = VGroup(
        *[
            Arrow(
                boxes[i].get_right(),
                boxes[i + 1].get_left(),
                buff=0.06,
                color=INK_3,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.3,
            )
            for i in range(len(boxes) - 1)
        ]
    )
    return boxes, links


class Plan(Scene):
    """The workflow as it exists in the code: named skills, and every outcome they declare."""

    def construct(self) -> None:
        """Run down the chain of skills, showing what each one can return."""
        heading = line("Four skills and a judge, camera to cut.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        # Each row is a skill in src/applications/pork_leg_alignment/skills/.
        steps = (
            ("perceive the leg", "estimate_leg_from_camera", ("none declared",)),
            ("choose the grip", "select_shank_grasp", ("none declared",)),
            (
                "close on the shank",
                "acquire_shank",
                ("unreachable", "closed on nothing", "slipped", "lift not achieved"),
            ),
            (
                "move it into line",
                "rotate_on_belt  /  pick_and_place",
                ("unreachable", "slipped", "misaligned", "released late", "dropped", "not lifted, carrying only"),
            ),
            ("score the cut", "sim/saw.py, the judge", ("offset or angle out of tolerance",)),
        )
        boxes = VGroup()
        for human, code, _ in steps:
            frame = Rectangle(width=6.2, height=1.08, color=RULE, stroke_width=2)
            name = line(human, size=ANNOT, color=INK)
            ident = figure(code, size=18, color=INK_3)
            name.move_to(frame.get_left() + RIGHT * 0.32 + UP * 0.22, aligned_edge=LEFT)
            ident.move_to(frame.get_left() + RIGHT * 0.32 + DOWN * 0.25, aligned_edge=LEFT)
            boxes.add(VGroup(frame, name, ident))
        boxes.arrange(DOWN, buff=0.24).move_to([-3.6, -0.3, 0])
        links = VGroup(
            *[
                Arrow(
                    boxes[i].get_bottom(),
                    boxes[i + 1].get_top(),
                    buff=0.05,
                    color=INK_3,
                    stroke_width=3,
                    max_tip_length_to_length_ratio=0.35,
                )
                for i in range(len(boxes) - 1)
            ]
        )
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * 0.2) for b in boxes], lag_ratio=0.14), run_time=1.8)
        self.play(LaggedStart(*[Create(x) for x in links], lag_ratio=0.2), run_time=1.2)
        self.wait(0.8)

        # Each skill declares what it can return, and every one of those is routed.
        says = line("Each skill declares what it can return.", size=ANNOT, color=INK_2)
        says.move_to([3.4, 2.6, 0])
        self.play(FadeIn(says), run_time=0.9)

        # One skill at a time, so the outcome chips never share a row.
        previous: VGroup | None = None
        for index, (_, _, outcomes) in enumerate(steps):
            chips = VGroup()
            for text in outcomes:
                chip = Rectangle(width=4.7, height=0.46, color=WARN, stroke_width=1.8)
                chips.add(VGroup(chip, figure(text, size=18, color=WARN).move_to(chip.get_center())))
            chips.arrange(DOWN, buff=0.12).move_to([3.4, 0.4, 0])
            lead = Arrow(
                boxes[index].get_right(),
                chips.get_left(),
                buff=0.14,
                color=WARN,
                stroke_width=2,
                max_tip_length_to_length_ratio=0.1,
            )
            group = VGroup(lead, chips)
            if previous is None:
                self.play(
                    Indicate(boxes[index][0], color=BLUE, scale_factor=1.03), Create(lead), FadeIn(chips), run_time=0.9
                )
            else:
                self.play(
                    Indicate(boxes[index][0], color=BLUE, scale_factor=1.03),
                    FadeOut(previous),
                    Create(lead),
                    FadeIn(chips),
                    run_time=0.9,
                )
            previous = group
            self.wait(0.5)

        routed = VGroup(
            line("Every outcome is routed.", size=ANNOT, color=BLUE),
            line("The runner adds two to every skill:", size=ANNOT, color=BLUE),
        ).arrange(DOWN, buff=0.14)
        routed_2 = line("precondition failed, success not verified.", size=ANNOT, color=BLUE)
        VGroup(routed, routed_2).arrange(DOWN, buff=0.14).move_to([3.4, -2.85, 0])
        self.play(FadeIn(routed), FadeIn(routed_2), run_time=1.1)
        self.wait(1.6)
        self.play(FadeOut(previous), FadeOut(says), FadeOut(routed), FadeOut(routed_2), run_time=0.7)

        # The one step with two strategies in it.
        highlight = Rectangle(width=6.2, height=1.08, color=BLUE, stroke_width=3).move_to(boxes[3][0].get_center())
        a_text = VGroup(
            figure("pick_and_place", size=ANNOT, color=BLUE),
            line("lift the shank 100 mm and carry the leg", size=18, color=INK_2),
        ).arrange(DOWN, buff=0.14)
        b_text = VGroup(
            figure("rotate_on_belt", size=ANNOT, color=BLUE),
            line("raise the shank 20 mm and swing the leg", size=18, color=INK_2),
        ).arrange(DOWN, buff=0.14)
        VGroup(a_text, b_text).arrange(DOWN, buff=0.75).move_to([3.4, 0.4, 0])
        self.play(Create(highlight, rate_func=EASE), run_time=0.8)
        self.play(LaggedStart(FadeIn(a_text), FadeIn(b_text), lag_ratio=0.4), run_time=1.5)
        built = line("I built both, and ran both on the", size=ANNOT, color=BLUE)
        built_2 = line("same 20 legs.", size=ANNOT, color=BLUE)
        VGroup(built, built_2).arrange(DOWN, buff=0.16).move_to([3.4, -2.6, 0])
        self.play(FadeIn(built), FadeIn(built_2), run_time=1.0)
        self.wait(2.2)


class Cameras(Scene):
    """The eye: a depth camera over the belt, and why this one."""

    def construct(self) -> None:
        """Place the camera, give the error law, then the two candidates."""
        self.add(belt())
        camera = Rectangle(width=1.5, height=0.5, fill_color=INK_2, fill_opacity=1, stroke_width=0)
        camera.move_to([0, 2.55, 0])
        cone = Polygon(
            [-0.7, 2.3, 0],
            [0.7, 2.3, 0],
            [3.0, BELT_BOTTOM, 0],
            [-3.0, BELT_BOTTOM, 0],
            fill_color=BLUE_SOFT,
            fill_opacity=0.5,
            stroke_width=0,
        )
        heading = line("A depth camera, 950 mm over the belt.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), FadeIn(camera), run_time=1.0)
        self.play(FadeIn(cone), run_time=0.9)
        piece = leg(2.4).rotate(20 * DEGREES).move_to([-0.4, 0.1, 0])
        self.play(FadeIn(piece), run_time=0.6)
        self.wait(0.8)

        maths = VGroup(
            line("Two infrared eyes a fixed distance apart. The shift between", size=ANNOT, color=INK_2),
            line("them gives the range, so the error grows with the square of it:", size=ANNOT, color=INK_2),
            figure("depth error  =  Z squared  x  subpixel  /  ( focal x baseline )", size=ANNOT, color=INK),
            figure("at Z = 0.95 m,  about 1.2 mm on the belt", size=ANNOT, color=BLUE),
        ).arrange(DOWN, buff=0.16)
        maths.move_to([0, -3.15, 0])
        self.play(FadeIn(maths[0]), FadeIn(maths[1]), run_time=1.1)
        self.play(Write(maths[2]), run_time=1.5)
        self.play(FadeIn(maths[3], shift=UP * 0.12), run_time=0.9)
        self.wait(2.0)
        self.play(*[FadeOut(m) for m in (maths, cone, camera, piece, heading)], run_time=0.8)
        self.clear()

        # The two candidates, on the numbers that decided it.
        pick = line("I modelled two real cameras and ran 20 legs in 9 poses each.", size=HEAD)
        pick.to_edge(UP, buff=0.5)
        self.play(FadeIn(pick, shift=DOWN * 0.15), run_time=1.1)

        rows = (
            ("", "Gemini 335L", "D455"),
            ("depth noise on the leg", "0.94 mm", "0.88 mm"),
            ("pixels on the shank", "7,531", "8,037"),
            ("leg in view, long side across", "158 / 180", "157 / 180"),
            ("washdown rating", "IP65", "none"),
        )
        table = VGroup()
        for index, (what, a, b) in enumerate(rows):
            head = index == 0
            y = 1.5 - 0.85 * index
            cells = VGroup(
                line(what, size=ANNOT, color=INK_2).move_to([-6.3, y, 0], aligned_edge=LEFT),
                figure(a, size=ANNOT, color=INK_2 if head else BLUE).move_to([0.4, y, 0], aligned_edge=LEFT),
                figure(b, size=ANNOT, color=INK_2 if head else INK).move_to([3.9, y, 0], aligned_edge=LEFT),
            )
            table.add(cells)
        rule_line = Line([-6.4, 1.15, 0], [6.6, 1.15, 0], color=RULE, stroke_width=1.5)
        for index, row in enumerate(table):
            self.play(FadeIn(row), run_time=0.5)
            if index == 0:
                self.play(Create(rule_line), run_time=0.4)
        self.wait(1.4)

        chosen = VGroup(
            line("The noise is 6 percent apart, too close to choose on.", size=ANNOT, color=INK_2),
            line("I took the Gemini 335L for its IP65 rating and hardware sync.", size=BODY, color=BLUE),
        ).arrange(DOWN, buff=0.2)
        chosen.move_to([0, -3.1, 0])
        self.play(FadeIn(chosen), run_time=1.0)
        self.wait(2.0)


class Segment(Scene):
    """Finding the leg in the frame, by height first and by a network where height fails."""

    def construct(self) -> None:
        """Height above the belt, then what it cannot do, then the learned answer."""
        heading = line("First, which pixels are leg.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        frame = Rectangle(width=6.4, height=3.6, color=RULE, stroke_width=2).move_to([-3.4, 0.2, 0])
        piece = leg(4.0).rotate(18 * DEGREES).move_to(frame.get_center())
        self.play(Create(frame), FadeIn(piece), run_time=1.1)

        rule_text = VGroup(
            line("The belt is flat and the leg is not.", size=BODY),
            line("Anything standing more than 10 mm", size=BODY),
            line("above the empty belt is a piece.", size=BODY),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        rule_text.move_to([3.6, 0.9, 0])
        self.play(FadeIn(rule_text), run_time=1.2)
        outline = piece.copy().set_fill(opacity=0).set_stroke(BLUE, width=3)
        self.play(Create(outline, rate_func=EASE), run_time=1.2)
        fast = figure("no training, 93 to 105 ms a frame", size=ANNOT, color=BLUE).move_to([3.6, -0.9, 0])
        self.play(FadeIn(fast), run_time=0.8)
        self.wait(1.6)

        # Where the rule fails.
        self.play(FadeOut(rule_text), FadeOut(fast), run_time=0.5)
        second = leg(4.0).rotate(-8 * DEGREES).move_to(frame.get_center() + RIGHT * 0.55 + DOWN * 0.75)
        self.play(FadeIn(second), run_time=0.7)
        joined = figure("two legs touching read as one", size=ANNOT, color=WARN).move_to([3.6, 0.6, 0])
        self.play(FadeIn(joined), Indicate(outline, color=WARN, scale_factor=1.02), run_time=1.1)
        self.wait(1.2)

        learned = VGroup(
            line("On plant footage a colour rule found", size=BODY, color=INK_2),
            figure("14 of 55 legs whole", size=BODY, color=WARN),
            line("Segment Anything plus the colour rule:", size=BODY, color=INK_2),
            figure("36 of 55", size=BODY, color=BLUE),
        ).arrange(DOWN, buff=0.22)
        learned.move_to([3.6, -1.0, 0])
        self.play(LaggedStart(*[FadeIn(x) for x in learned], lag_ratio=0.25), run_time=2.0)
        self.wait(1.6)

        keep = line("So the U-Net segments, and geometry checks it every frame.", size=BODY, color=BLUE)
        keep.move_to([0, -3.3, 0])
        self.play(FadeIn(keep), run_time=1.1)
        self.wait(2.2)


class CentreOfGravity(Scene):
    """The pivot: three ways to find it, and what each one costs."""

    def construct(self) -> None:
        """Outline centre, column centroid, learned correction, with the numbers."""
        heading = line("The turn happens about the centre of gravity.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        length = 6.6
        piece = leg(length).move_to([-2.9, 1.2, 0])
        # The bounding box is centred at half the length; the centre of gravity is short of that.
        base = piece.get_center() + RIGHT * (COG_FRACTION - 0.5) * length
        self.play(FadeIn(piece), run_time=0.7)

        # One legend row under the leg; each dot on the leg takes its colour from its entry.
        def entry(colour: str, text: str) -> VGroup:
            return VGroup(Dot(radius=0.09, color=colour), figure(text, size=ANNOT, color=colour)).arrange(
                RIGHT, buff=0.18
            )

        truth = Dot(base, radius=0.1, color=INK)
        truth_entry = entry(INK, "true centre of mass")
        outline_centre = Dot(base + RIGHT * 39.6 / 722 * length, radius=0.1, color=WARN)
        outline_entry = entry(WARN, "outline centre: 39.6 mm off")
        column = Dot(base + RIGHT * 7.9 / 722 * length, radius=0.1, color=BLUE)
        column_entry = entry(BLUE, "column centroid: 7.9 mm off")
        legend = VGroup(truth_entry, outline_entry, column_entry).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        legend.move_to([1.3, 1.55, 0], aligned_edge=LEFT)
        scale_note = annot("dots at median error").next_to(legend, DOWN, buff=0.35).align_to(legend, LEFT)

        self.play(FadeIn(truth), FadeIn(truth_entry), run_time=0.9)
        self.play(FadeIn(outline_centre), FadeIn(outline_entry), FadeIn(scale_note), run_time=1.0)
        self.wait(1.0)

        maths = (
            VGroup(
                line("The camera sees only the top. Treat each pixel as a column of", size=ANNOT, color=INK_2),
                line("meat from the belt up, and take the centre of all that volume:", size=ANNOT, color=INK_2),
                figure("centre  =  sum( height x position )  /  sum( height )", size=BODY, color=INK),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -2.3, 0])
        )
        self.play(FadeIn(maths[0]), FadeIn(maths[1]), run_time=1.0)
        self.play(Write(maths[2]), run_time=1.6)
        self.play(FadeIn(column), FadeIn(column_entry), run_time=1.0)
        self.wait(1.6)

        self.play(FadeOut(maths), run_time=0.6)
        correction = (
            VGroup(
                line("A small network, 208,000 weights, three minutes to train,", size=ANNOT, color=INK_2),
                line("learns what the geometry misses and moves the answer:", size=ANNOT, color=INK_2),
                figure("estimate  =  column centroid  +  network( height map )", size=ANNOT, color=INK),
                figure("1.2 mm on the median frame, 4.6 mm at worst", size=BODY, color=BLUE),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -2.35, 0])
        )
        self.play(FadeIn(correction[0]), FadeIn(correction[1]), run_time=1.0)
        self.play(Write(correction[2]), run_time=1.5)
        self.play(
            column.animate.move_to(base + RIGHT * 1.2 / 722 * length),
            FadeIn(correction[3], shift=UP * 0.12),
            run_time=1.2,
        )
        self.wait(1.4)
        why = line("Zero output is the geometry exactly, so a bad model falls back to it.", size=ANNOT, color=INK_2)
        why.move_to([0, -3.55, 0])
        self.play(FadeIn(why), run_time=1.0)
        self.wait(2.2)


# The cell top-down, to scale, as the code has it: the belt runs in +x, its far edge
# is at world y 0.85 m (the rail's inner face at 0.857) and the open edge at 0.15 m, and the saw's blade plane runs
# along the belt 0.03 m past the open edge. A leg is aligned when it points across
# the belt toward the open edge (heading -90 degrees) with its hock on that plane.
CELL_SCALE = 4.6  # frame units per metre
RAIL_Y_M, EDGE_Y_M, PLANE_Y_M = 0.85, 0.15, 0.12
SAW_X_M = 1.95


def cell_point(x_m: float, y_m: float) -> np.ndarray:
    """A point on the cell floor, world metres to frame units."""
    return np.array([(x_m - 0.95) * CELL_SCALE, (y_m - 0.5) * CELL_SCALE + 0.35, 0.0])


def cell_belt() -> VGroup:
    """The belt between its rail and its open edge, the saw, and the blade plane."""
    left, right = cell_point(-0.62, 0.5)[0], cell_point(2.52, 0.5)[0]
    top, bottom = cell_point(0, RAIL_Y_M)[1], cell_point(0, EDGE_Y_M)[1]
    surface = Rectangle(width=right - left, height=top - bottom, fill_color=BELT, fill_opacity=1, stroke_width=0)
    surface.move_to([(left + right) / 2, (top + bottom) / 2, 0])
    rail = Line([left, top, 0], [right, top, 0], color=INK_3, stroke_width=4)
    edge = Line([left, bottom, 0], [right, bottom, 0], color=RULE, stroke_width=2)
    plane_y = cell_point(0, PLANE_Y_M)[1]
    plane = DashedLine(
        [cell_point(1.35, 0)[0], plane_y, 0], [right, plane_y, 0], color=BLUE, stroke_width=2.5, dash_length=0.14
    )
    saw = Rectangle(width=0.62 * CELL_SCALE, height=0.1, fill_color=BLUE, fill_opacity=1, stroke_width=0)
    saw.move_to(cell_point(SAW_X_M, PLANE_Y_M))
    labels = VGroup(
        annot("far rail").next_to(rail, UP, buff=0.12).align_to(rail, LEFT).shift(RIGHT * 0.75),
        annot("open edge").next_to(edge, DOWN, buff=0.12).align_to(edge, LEFT).shift(RIGHT * 0.75),
        annot("saw", BLUE).next_to(saw, DOWN, buff=0.34).shift(RIGHT * 1.9),
        annot("blade plane", BLUE).move_to([cell_point(1.55, 0)[0], plane_y - 0.3, 0]),
    )
    return VGroup(surface, rail, edge, plane, saw, labels)


def leg_split(length: float) -> VGroup:
    """A leg in two parts that meet at the hock, so the saw can take the foot off.

    Index 0 is the ham and shank, index 1 the foot. The group's centre of rotation for
    the turn is the centre of gravity, which the caller tracks with `leg_point`.
    """
    fractions = [f for f, _ in LEG_SECTIONS]
    upper = [leg_point(length, f, 1.0) for f in fractions if f <= HOCK_FRACTION] + [
        leg_point(length, HOCK_FRACTION, 1.0)
    ]
    lower = [leg_point(length, HOCK_FRACTION, -1.0)] + [
        leg_point(length, f, -1.0) for f in reversed(fractions) if f <= HOCK_FRACTION
    ]
    body = VMobject(fill_color=MEAT, fill_opacity=1, stroke_width=0)
    body.set_points_smoothly([*upper, *lower, upper[0]])
    foot_upper = [leg_point(length, HOCK_FRACTION, 1.0)] + [
        leg_point(length, f, 1.0) for f in fractions if f > HOCK_FRACTION
    ]
    foot_lower = [leg_point(length, f, -1.0) for f in reversed(fractions) if f > HOCK_FRACTION] + [
        leg_point(length, HOCK_FRACTION, -1.0)
    ]
    foot = VMobject(fill_color=MEAT, fill_opacity=0.82, stroke_width=0)
    foot.set_points_smoothly([*foot_upper, *foot_lower, foot_upper[0]])
    return VGroup(body, foot)


class Grippers(Scene):
    """The two grippers tested, how hard each holds, and why only one straddles a shank."""

    def construct(self) -> None:
        """Hold forces first, then the geometry that rules the three-finger gripper out."""
        heading = line("I tested two grippers on the leg.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        # A parallel jaw and a centric three-finger gripper, seen from below.
        jaw = VGroup(
            Rectangle(width=0.34, height=1.7, fill_color=BLUE, fill_opacity=1, stroke_width=0).shift(LEFT * 0.95),
            Rectangle(width=0.34, height=1.7, fill_color=BLUE, fill_opacity=1, stroke_width=0).shift(RIGHT * 0.95),
        ).move_to([-3.6, 1.0, 0])
        ring = Circle(radius=0.95, color=RULE, stroke_width=1.5).move_to([3.6, 1.0, 0])
        fingers = VGroup(
            *[
                Dot(ring.get_center() + 0.95 * np.array([np.cos(a), np.sin(a), 0.0]), radius=0.17, color=BLUE)
                for a in (np.pi / 2, np.pi / 2 + 2 * np.pi / 3, np.pi / 2 + 4 * np.pi / 3)
            ]
        )
        names = VGroup(
            line("parallel jaw", size=ANNOT, color=INK).next_to(jaw, DOWN, buff=0.4),
            line("three-finger, centric", size=ANNOT, color=INK).next_to(ring, DOWN, buff=0.4),
        )
        self.play(FadeIn(jaw), Create(ring), FadeIn(fingers), FadeIn(names), run_time=1.2)

        holds = VGroup(
            figure("held 918 N, needed 720 N", size=ANNOT, color=INK_2).next_to(names[0], DOWN, buff=0.3),
            figure("held 229 N, needed 180 N", size=ANNOT, color=INK_2).next_to(names[1], DOWN, buff=0.3),
        )
        self.play(FadeIn(holds), run_time=0.9)
        both = line("Both pass the pull test.", size=BODY, color=INK_2).move_to([0, -2.1, 0])
        self.play(FadeIn(both), run_time=0.8)
        self.wait(1.6)
        self.play(FadeOut(both), FadeOut(holds), FadeOut(jaw), FadeOut(names[0]), run_time=0.7)

        # Why the three-finger gripper cannot straddle a shank lying on the belt.
        group = VGroup(ring, fingers, names[1])
        self.play(group.animate.move_to([-2.4, 0.6, 0]).scale(1.35), run_time=1.0)
        centre = ring.get_center()
        radius = ring.width / 2
        shank = Rectangle(
            width=2 * radius * 1.1, height=0.62 * radius * 1.1 * 1.6, fill_color=MEAT, fill_opacity=0.9, stroke_width=0
        ).move_to(centre)
        shank.set_z_index(-1)
        dim_x = centre[0] - radius * 1.3
        half = VGroup(
            Line([dim_x, centre[1], 0], [dim_x, centre[1] - radius / 2, 0], color=WARN, stroke_width=3),
            Line([dim_x - 0.1, centre[1], 0], [dim_x + 0.1, centre[1], 0], color=WARN, stroke_width=3),
            Line(
                [dim_x - 0.1, centre[1] - radius / 2, 0],
                [dim_x + 0.1, centre[1] - radius / 2, 0],
                color=WARN,
                stroke_width=3,
            ),
            annot("r / 2", WARN).move_to([dim_x - 0.75, centre[1] - radius / 4, 0]),
        )
        self.play(FadeIn(shank), run_time=0.8)
        rule = VGroup(
            line("Two of its fingers sit half the open radius from the axis.", size=ANNOT, color=INK_2),
            line("So it fits a shank only as wide as half its opening:", size=ANNOT, color=INK_2),
            figure("shank width  <=  opening / 2  =  77.5 mm", size=BODY, color=INK),
            figure("shanks here are 78 to 110 mm", size=BODY, color=WARN),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.24)
        rule.move_to([0.2, 0.7, 0], aligned_edge=LEFT)
        if rule.get_right()[0] > 6.8:
            rule.scale_to_fit_width(6.6)
            rule.move_to([0.2, 0.7, 0], aligned_edge=LEFT)
        self.play(Create(half), FadeIn(rule[0]), FadeIn(rule[1]), run_time=1.2)
        self.play(Write(rule[2]), run_time=1.1)
        self.play(FadeIn(rule[3], shift=UP * 0.1), run_time=0.8)
        self.wait(1.6)

        outcome = (
            VGroup(
                line("It refuses before the arm moves. It works end-on at the trotter,", size=ANNOT, color=INK_2),
                line("which needs a tool that tilts: the UR20 can, the SR-20iA cannot.", size=ANNOT, color=INK_2),
                line("So the cell uses the parallel jaw on the shank.", size=BODY, color=BLUE),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -2.75, 0])
        )
        self.play(LaggedStart(*[FadeIn(o) for o in outcome], lag_ratio=0.35), run_time=1.8)
        self.wait(2.2)


class Arms(Scene):
    """Two arm types, measured on the same reach grid and the same wrist load."""

    def construct(self) -> None:
        """Reach counts by height, then the wrist rating a carried leg exceeds."""
        heading = line("A six-axis arm and a SCARA, on the same reach test.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        arms = VGroup(six_axis(3.0), scara(3.0)).arrange(RIGHT, buff=0.8, aligned_edge=DOWN).move_to([-3.55, 0.25, 0])
        arm_names = VGroup(
            line("UR20", size=ANNOT).next_to(arms[0], DOWN, buff=0.22),
            line("SR-20iA", size=ANNOT).next_to(arms[1], DOWN, buff=0.22),
        )
        self.play(FadeIn(arms), FadeIn(arm_names), run_time=1.1)

        grid_note = line("120 belt points, tool pointing down, three heights", size=ANNOT, color=INK_2)
        grid_note.move_to([0.45, 2.6, 0], aligned_edge=LEFT)
        legend = VGroup(
            Rectangle(width=0.32, height=0.22, fill_color=BLUE, fill_opacity=1, stroke_width=0),
            figure("UR20", size=18, color=INK_2),
            Rectangle(width=0.32, height=0.22, fill_color=INK_3, fill_opacity=1, stroke_width=0),
            figure("SR-20iA", size=18, color=INK_2),
        ).arrange(RIGHT, buff=0.18)
        legend[2].shift(RIGHT * 0.3)
        legend[3].shift(RIGHT * 0.3)
        legend.move_to([0.45, 2.1, 0], aligned_edge=LEFT)
        self.play(FadeIn(grid_note), FadeIn(legend), run_time=0.8)
        rows = (("50 mm", 120, 101), ("180 mm", 120, 101), ("350 mm", 120, 0))
        full = 4.0
        for index, (height, ur, sr) in enumerate(rows):
            y = 1.2 - index * 1.15
            name = figure(height, size=ANNOT, color=INK_2).move_to([0.45, y, 0], aligned_edge=LEFT)
            ur_bar = Rectangle(width=full * ur / 120, height=0.28, fill_color=BLUE, fill_opacity=1, stroke_width=0)
            ur_bar.move_to([2.0, y + 0.21, 0], aligned_edge=LEFT)
            sr_bar = Rectangle(
                width=max(full * sr / 120, 0.03), height=0.28, fill_color=INK_3, fill_opacity=1, stroke_width=0
            )
            sr_bar.move_to([2.0, y - 0.21, 0], aligned_edge=LEFT)
            ur_value = figure(f"{ur}", size=18, color=INK).next_to(ur_bar, RIGHT, buff=0.15)
            sr_value = figure(f"{sr}", size=18, color=INK).next_to(sr_bar, RIGHT, buff=0.15)
            self.play(
                FadeIn(name),
                FadeIn(ur_bar, shift=RIGHT * 0.2),
                FadeIn(sr_bar, shift=RIGHT * 0.2),
                FadeIn(ur_value),
                FadeIn(sr_value),
                run_time=0.7,
            )
        self.wait(1.4)

        wrist = (
            VGroup(
                line("Carrying a leg loads the SCARA's wrist past its rating:", size=ANNOT, color=INK_2),
                figure("0.6 to 1.6 kg m^2 measured, 0.45 kg m^2 rated", size=BODY, color=WARN),
                line("The SCARA is 0.2 to 0.5 s faster per leg where it reaches.", size=ANNOT, color=INK_2),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -2.95, 0])
        )
        self.play(LaggedStart(*[FadeIn(w) for w in wrist], lag_ratio=0.35), run_time=1.6)
        self.wait(2.4)


class Method(Scene):
    """The method on the real cell layout: perceive, grip, intercept, turn, cut."""

    def construct(self) -> None:
        """One leg, start to finish, drawn to scale with the belt as the code has it."""
        heading = line("One leg through the cell, drawn to scale.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)
        cell = cell_belt()
        self.play(FadeIn(cell), run_time=1.0)
        speed = VGroup(
            Arrow(
                cell_point(0.25, 0.95),
                cell_point(0.65, 0.95),
                buff=0,
                color=INK_3,
                stroke_width=3,
                max_tip_length_to_length_ratio=0.25,
            ),
            annot("0.30 m/s"),
        )
        speed[1].next_to(speed[0], RIGHT, buff=0.15)
        self.play(FadeIn(speed), run_time=0.6)

        length = 0.722 * CELL_SCALE
        yaw = 38 * DEGREES
        cog_start = cell_point(0.05, 0.52)
        piece = leg_split(length)
        piece.rotate(yaw, about_point=np.zeros(3)).shift(cog_start)
        cog = Dot(cog_start, radius=0.07, color=BLUE)
        self.play(FadeIn(piece), run_time=0.7)

        def say(text: str) -> Text:
            return line(text, size=ANNOT, color=INK_2).move_to([0, -3.35, 0])

        caption = say("1. Perceive: the outline, its axis and the centre of gravity.")
        direction = np.array([np.cos(yaw), np.sin(yaw), 0.0])
        axis = DashedLine(
            cog_start - direction * COG_FRACTION * length,
            cog_start + direction * (1 - COG_FRACTION) * length,
            color=INK_3,
            stroke_width=2,
            dash_length=0.1,
        )
        self.play(FadeIn(caption), Create(axis), FadeIn(cog), run_time=1.0)
        self.wait(0.8)

        grasp_point = cog_start + direction * (GRASP_FRACTION - COG_FRACTION) * length
        grasp_dot = Dot(grasp_point, radius=0.07, color=BLUE)
        new_caption = say("2. Choose the grip: the shank, seven tenths along the axis.")
        self.play(ReplacementTransform(caption, new_caption), FadeIn(grasp_dot), run_time=0.9)
        caption = new_caption
        self.wait(0.6)

        # The belt carries the leg while the arm reaches for a point that keeps moving.
        travel = 0.3 * CELL_SCALE
        new_caption = say("3. Intercept: meet the grip point where the belt will have carried it.")
        maths = figure("meet at  p(t)  =  p0  +  v t", size=ANNOT, color=INK).move_to([3.9, -2.45, 0])
        moving = VGroup(piece, cog, axis, grasp_dot)
        self.play(ReplacementTransform(caption, new_caption), FadeIn(maths), run_time=0.8)
        caption = new_caption
        grip = jaws(0.62, height=0.52).rotate(yaw + np.pi / 2).move_to(grasp_point + RIGHT * travel + UP * 0.6)
        self.play(moving.animate.shift(RIGHT * travel), FadeIn(grip), run_time=1.3, rate_func=rate_functions.linear)
        self.play(grip.animate.move_to(grasp_dot.get_center()), run_time=0.6, rate_func=EASE)
        self.play(jaws_close(grip), run_time=0.5)
        met = figure("met within 1 mm at 0.30 m/s", size=18, color=BLUE).next_to(maths, DOWN, buff=0.15)
        self.play(FadeIn(met), run_time=0.6)
        self.wait(0.6)
        self.play(FadeOut(maths), FadeOut(met), FadeOut(axis), FadeOut(grasp_dot), run_time=0.5)

        # The turn: square across the belt, hock on the blade plane.
        new_caption = say("4. Turn about the centre of gravity until the hock sits on the blade plane.")
        goal = (
            VGroup(
                figure("heading after the turn  =  -90 degrees", size=18, color=INK),
                figure("hock after the turn     =  on the blade plane", size=18, color=INK),
            )
            .arrange(DOWN, aligned_edge=LEFT, buff=0.14)
            .move_to([3.3, -2.5, 0])
        )
        self.play(ReplacementTransform(caption, new_caption), FadeIn(goal), run_time=0.9)
        caption = new_caption
        held = VGroup(piece, cog, grip)
        centre_now = cog.get_center()
        turn = -90 * DEGREES - yaw
        hock_offset = (HOCK_FRACTION - COG_FRACTION) * length
        target_centre = np.array([centre_now[0] + 0.55 * CELL_SCALE, cell_point(0, PLANE_Y_M)[1] + hock_offset, 0])
        held.save_state()

        def turn_and_slide(mob: VGroup, alpha: float) -> None:
            mob.restore()
            mob.rotate(alpha * turn, about_point=centre_now)
            mob.shift(alpha * (target_centre - centre_now))

        self.play(UpdateFromAlphaFunc(held, turn_and_slide), run_time=2.4, rate_func=EASE)
        hock_mark = Dot(target_centre + DOWN * hock_offset, radius=0.07, color=WARN)
        self.play(FadeIn(hock_mark), Flash(hock_mark.get_center(), color=BLUE, line_length=0.18), run_time=0.7)

        new_caption = say("5. Look again. More than 3 mm or 1 degree off, and it turns again.")
        self.play(ReplacementTransform(caption, new_caption), FadeOut(goal), run_time=0.8)
        caption = new_caption
        self.wait(0.9)

        # Release, and the belt carries the leg into the saw, which takes the foot off at the hock.
        new_caption = say("6. Let go. The saw cuts the plane, and the foot comes off at the joint.")
        self.play(ReplacementTransform(caption, new_caption), FadeOut(grip), run_time=0.8)
        caption = new_caption
        to_saw = cell_point(SAW_X_M, 0)[0] - target_centre[0]
        leg_and_marks = VGroup(piece, cog, hock_mark)
        self.play(leg_and_marks.animate.shift(RIGHT * to_saw), run_time=2.0, rate_func=rate_functions.linear)
        cut = Line(
            hock_mark.get_center() + LEFT * 0.5, hock_mark.get_center() + RIGHT * 0.5, color=WARN, stroke_width=4
        )
        self.play(Create(cut), run_time=0.4)
        self.play(piece[1].animate.shift(DOWN * 0.55).set_opacity(0.45), FadeOut(cut), run_time=0.9, rate_func=EASE)

        result = figure("any heading, UR20:  hock 1.1 mm median, 1.7 mm worst", size=ANNOT, color=BLUE)
        result.move_to(caption.get_center())
        self.play(ReplacementTransform(caption, result), run_time=0.9)
        self.wait(2.4)


class Teach(Scene):
    """What learns in the cell, and how a skill gets taught through its contract."""

    def construct(self) -> None:
        """Learned parts on rules, the teaching path step by step, then where labels come from."""
        heading = line("Three learned parts, two trained so far.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)

        parts = (
            ("leg segmenter", "sits on height above the belt", True),
            ("centre-of-gravity correction", "sits on the column centroid", True),
            ("grasp offsets", "sit on the shank rule", False),
        )
        columns = VGroup()
        for name, base, trained in parts:
            model = Rectangle(width=4.4, height=0.8, color=BLUE if trained else RULE, stroke_width=2)
            rule_box = Rectangle(width=4.4, height=0.8, color=RULE, stroke_width=2)
            VGroup(model, rule_box).arrange(DOWN, buff=0.0)
            model_name = figure(name, size=18, color=BLUE if trained else INK_2).move_to(model.get_center())
            rule_name = line(base, size=18, color=INK_2).move_to(rule_box.get_center())
            columns.add(VGroup(model, rule_box, model_name, rule_name))
        columns.arrange(RIGHT, buff=0.2).move_to([0, 1.55, 0])
        not_yet = line("not trained yet", size=18, color=WARN).next_to(columns[2], DOWN, buff=0.22)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.15) for c in columns], lag_ratio=0.2), run_time=1.5)
        self.play(FadeIn(not_yet), run_time=0.6)
        zero = line(
            "Each predicts a correction to its rule. A zero output is the rule exactly.", size=ANNOT, color=INK_2
        )
        zero.move_to([0, -0.25, 0])
        self.play(FadeIn(zero), run_time=0.9)
        self.wait(1.6)
        self.play(*[FadeOut(m) for m in (columns, not_yet, zero, heading)], run_time=0.7)

        teach = line("Teaching a new skill goes through its contract.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(teach, shift=DOWN * 0.15), run_time=0.9)
        steps = (
            ("run the skill", "a script, a candidate grid, later a person"),
            ("record each run", "its inputs, the action, the outcome's numbers"),
            ("write the dataset record", "source, robot, date, episodes, known issues"),
            ("train", "weights the ROS 2 node can load"),
            ("apply the gate set first", "the model replaces the rule only if it wins, paired by leg"),
        )
        boxes = VGroup()
        details = VGroup()
        for index, (name, detail) in enumerate(steps):
            y = 2.2 - index * 1.0
            frame = Rectangle(width=5.5, height=0.72, color=RULE, stroke_width=2).move_to([-3.95, y, 0])
            boxes.add(VGroup(frame, figure(name, size=ANNOT, color=INK).move_to(frame.get_center())))
            details.add(line(detail, size=ANNOT, color=INK_2).move_to([-0.95, y, 0], aligned_edge=LEFT))
        arrows = VGroup(
            *[
                Arrow(
                    boxes[i].get_bottom(),
                    boxes[i + 1].get_top(),
                    buff=0.04,
                    color=INK_3,
                    stroke_width=2.5,
                    max_tip_length_to_length_ratio=0.5,
                )
                for i in range(len(boxes) - 1)
            ]
        )
        for index in range(len(steps)):
            animations = [FadeIn(boxes[index], shift=RIGHT * 0.15), FadeIn(details[index])]
            if index:
                animations.append(Create(arrows[index - 1]))
            self.play(*animations, run_time=0.6)
        self.wait(1.4)
        self.play(*[FadeOut(m) for m in (boxes, details, arrows)], run_time=0.7)

        labels = (
            VGroup(
                line("In the plant the skill's own checks label its runs:", size=BODY, color=INK),
                figure("jaw opening   proof lift   pose at release   the cut", size=BODY, color=BLUE),
                line(
                    "They score the action taken, not the best one, so that label is weaker.", size=ANNOT, color=INK_2
                ),
            )
            .arrange(DOWN, buff=0.45)
            .move_to([0, 0.4, 0])
        )
        self.play(FadeIn(labels[0]), run_time=0.8)
        self.play(Write(labels[1]), run_time=1.2)
        self.play(FadeIn(labels[2]), run_time=0.9)
        self.wait(2.2)


class Reinforce(Scene):
    """Where reinforcement learning earns a place in this cell: a residual on the turn."""

    def construct(self) -> None:
        """Why only the turn, the residual on a scripted base, the reward, and the budget."""
        heading = line("Reinforcement learning goes in one place: the turn.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)
        why = (
            VGroup(
                line(
                    "The grip is a one-shot choice the simulator can score for every candidate.",
                    size=ANNOT,
                    color=INK_2,
                ),
                line("The turn is contact, a draping trotter, and 20 different legs.", size=ANNOT, color=INK_2),
            )
            .arrange(DOWN, buff=0.16)
            .move_to([0, 2.45, 0])
        )
        self.play(FadeIn(why), run_time=1.1)
        self.wait(1.0)

        def block(name: str, detail: str, width: float, colour: str, x: float) -> VGroup:
            frame = Rectangle(width=width, height=1.15, color=colour, stroke_width=2.5).move_to([x, 0.75, 0])
            text = (
                VGroup(
                    figure(name, size=ANNOT, color=colour if colour == BLUE else INK),
                    line(detail, size=18, color=INK_2),
                )
                .arrange(DOWN, buff=0.12)
                .move_to(frame.get_center())
            )
            return VGroup(frame, text)

        base = block("scripted turn", "about the centre of gravity", 4.1, RULE, -4.65)
        residual = block("residual policy", "a small, bounded correction", 4.1, BLUE, 0.05)
        out = block("the arm's action", "sent to the arm", 3.9, INK_2, 4.95)
        plus = figure("+", size=HEAD, color=INK).move_to([-2.3, 0.75, 0])
        feed = Arrow(
            residual.get_right(),
            out.get_left(),
            buff=0.1,
            color=INK_3,
            stroke_width=3,
            max_tip_length_to_length_ratio=0.3,
        )
        self.play(FadeIn(base), run_time=0.7)
        self.play(FadeIn(plus), FadeIn(residual), run_time=0.8)
        self.play(Create(feed), FadeIn(out), run_time=0.8)

        maths = (
            VGroup(
                figure("action  =  scripted(state)  +  clip(residual(state), bound)", size=ANNOT, color=INK),
                figure("reward  =  1 if every check in the contract passes, else 0", size=ANNOT, color=INK),
            )
            .arrange(DOWN, aligned_edge=LEFT, buff=0.22)
            .move_to([0, -0.9, 0])
        )
        self.play(Write(maths[0]), run_time=1.3)
        self.play(Write(maths[1]), run_time=1.3)
        same = line("The reward is the evaluator, so the two cannot disagree.", size=ANNOT, color=BLUE)
        same.move_to([0, -1.9, 0])
        self.play(FadeIn(same), run_time=0.8)
        self.wait(1.2)
        budget = (
            VGroup(
                line(
                    "To be trained over friction 0.15 to 0.5, belt 0.20 to 0.40 m/s, and yaw up to 35 degrees.",
                    size=ANNOT,
                    color=INK_2,
                ),
                line(
                    "One CPU runs about 21 policy steps a second, so 160,000 steps take about 2.1 hours.",
                    size=ANNOT,
                    color=INK_2,
                ),
            )
            .arrange(DOWN, buff=0.18)
            .move_to([0, -2.95, 0])
        )
        self.play(FadeIn(budget), run_time=1.1)
        self.wait(2.6)


class Foundation(Scene):
    """What a vision-language-action model adds, what it costs on a moving belt, and how it stays checked."""

    def construct(self) -> None:
        """Gains, costs in belt millimetres, and the contract wrapped around it."""
        heading = line("A foundation model as a base for new skills.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        gives = VGroup(
            line("It brings two things the cell does not have:", size=BODY, color=INK),
            line("manipulation before any demonstration on our product,", size=BODY, color=BLUE),
            line("and switching tasks with a sentence.", size=BODY, color=BLUE),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.2)
        gives.move_to([-6.2, 1.95, 0], aligned_edge=LEFT)
        self.play(LaggedStart(*[FadeIn(g) for g in gives], lag_ratio=0.3), run_time=1.5)
        self.wait(1.2)

        # Its latency, drawn as the belt it lets go by.
        mm = 0.048
        belt_line = Line([-5.8, -0.25, 0], [5.8, -0.25, 0], color=RULE, stroke_width=2)
        pi0 = Rectangle(width=22 * mm, height=0.36, fill_color=BLUE, fill_opacity=1, stroke_width=0)
        oft = Rectangle(width=96 * mm, height=0.36, fill_color=WARN, fill_opacity=1, stroke_width=0)
        pi0.move_to([-5.8, 0.25, 0], aligned_edge=LEFT)
        oft.move_to([-5.8, -0.75, 0], aligned_edge=LEFT)
        pi0_name = figure("22 mm: one pi0 inference on a 4090", size=18, color=INK).next_to(pi0, RIGHT, buff=0.3)
        oft_name = figure("96 mm: one OpenVLA-OFT chunk, three cameras", size=18, color=INK).next_to(
            oft, RIGHT, buff=0.3
        )
        belt_note = annot("belt travel at 0.30 m/s").move_to([-5.8, 0.75, 0], aligned_edge=LEFT)
        self.play(Create(belt_line), FadeIn(belt_note), run_time=0.5)
        self.play(FadeIn(pi0, shift=RIGHT * 0.2), FadeIn(pi0_name), run_time=0.8)
        self.play(FadeIn(oft, shift=RIGHT * 0.2), FadeIn(oft_name), run_time=0.8)
        planned = line(
            "A known latency can be planned around. The model needs a 14 to 24 GB GPU in a washdown cell.",
            size=18,
            color=INK_2,
        )
        planned.move_to([0, -1.55, 0])
        self.play(FadeIn(planned), run_time=0.9)
        self.wait(1.4)

        wrap = (
            VGroup(
                line("No such model carries a success test or a precondition.", size=ANNOT, color=INK_2),
                line(
                    "The contract adds them from outside, so its checks still run after the model acts.",
                    size=ANNOT,
                    color=BLUE,
                ),
                line("For aligning legs the small models stay at the base.", size=18, color=INK_3),
                line("For the plant's next jobs, this is the base worth testing.", size=18, color=INK_3),
            )
            .arrange(DOWN, buff=0.16)
            .move_to([0, -2.95, 0])
        )
        self.play(LaggedStart(*[FadeIn(w) for w in wrap], lag_ratio=0.35), run_time=1.8)
        self.wait(2.6)


class Hierarchy(Scene):
    """Skills as options, stacked into jobs and a plant, with a sub-goal passed down."""

    def construct(self) -> None:
        """Build the tree from primitives up, then light one sub-goal's path."""
        heading = line("The whole plant as one graph of sub-goals.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=0.9)
        option = (
            VGroup(
                line(
                    "A skill with a contract is an option in hierarchical reinforcement learning:",
                    size=ANNOT,
                    color=INK_2,
                ),
                figure("option  =  ( where it may start,  its policy,  when it ends )", size=ANNOT, color=INK),
                line("Sutton, Precup and Singh, 1999", size=18, color=INK_3),
            )
            .arrange(DOWN, buff=0.14)
            .move_to([0, 2.35, 0])
        )
        self.play(FadeIn(option[0]), run_time=0.8)
        self.play(Write(option[1]), FadeIn(option[2]), run_time=1.2)
        self.wait(1.0)

        def node(text: str, width: float, colour: str = RULE) -> VGroup:
            frame = Rectangle(width=width, height=0.66, color=colour, stroke_width=2)
            return VGroup(frame, figure(text, size=18, color=INK).move_to(frame.get_center()))

        plant = node("plant", 2.6, BLUE).move_to([0, 0.95, 0])
        jobs = (
            VGroup(node("leg cell", 2.8), node("loin puller infeed", 4.0))
            .arrange(RIGHT, buff=2.2)
            .move_to([0, -0.05, 0])
        )
        composed = node("align a piece for the next machine", 6.0, BLUE).move_to([0, -1.05, 0])
        primitives = (
            VGroup(*[node(t, 2.4) for t in ("perceive", "select grasp", "acquire", "turn on belt", "pick and place")])
            .arrange(RIGHT, buff=0.16)
            .move_to([0, -2.05, 0])
        )
        edges = VGroup(
            *[Line(plant.get_bottom(), j.get_top(), color=INK_3, stroke_width=1.8) for j in jobs],
            *[Line(j.get_bottom(), composed.get_top(), color=INK_3, stroke_width=1.8) for j in jobs],
            *[Line(composed.get_bottom(), pr.get_top(), color=INK_3, stroke_width=1.8) for pr in primitives],
        )
        self.play(LaggedStart(*[FadeIn(pr, shift=UP * 0.12) for pr in primitives], lag_ratio=0.1), run_time=1.2)
        self.play(FadeIn(composed), Create(edges[4:]), run_time=0.9)
        self.play(FadeIn(jobs), Create(edges[2:4]), run_time=0.9)
        self.play(FadeIn(plant), Create(edges[:2]), run_time=0.8)
        shared = line("Both jobs share the graph. The loin job changes the sub-goals.", size=ANNOT, color=BLUE)
        shared.move_to([0, -3.0, 0])
        self.play(FadeIn(shared), run_time=0.9)
        self.wait(1.4)

        path = VGroup(
            Line(jobs[0].get_bottom(), composed.get_top(), color=BLUE, stroke_width=7),
            Line(composed.get_bottom(), primitives[3].get_top(), color=BLUE, stroke_width=7),
        )
        goal_text = figure("cut in tolerance  ->  hock on the blade plane, heading -90", size=ANNOT, color=BLUE)
        goal_text.move_to([0, -3.0, 0])
        self.play(FadeOut(shared), jobs[0][0].animate.set_stroke(BLUE, width=4), run_time=0.5)
        self.play(Create(path[0]), composed[0].animate.set_stroke(BLUE, width=4), run_time=0.6)
        self.play(Create(path[1]), primitives[3][0].animate.set_stroke(BLUE, width=4), FadeIn(goal_text), run_time=0.8)
        self.wait(1.2)
        up_text = figure("each level judges the one below by its declared outcome", size=ANNOT, color=INK_2)
        up_text.move_to([0, -3.45, 0])
        self.play(FadeIn(up_text), run_time=0.9)
        self.wait(2.4)


class Numbers(Scene):
    """Every condition of the 220 saw-judged runs, and where the misses came from."""

    def construct(self) -> None:
        """Two panels of bars, one per arrival set, then the two causes of loss."""
        heading = line("220 runs in simulation, 20 legs a condition, judged by the saw.", size=HEAD)
        heading.to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)

        sets = (
            (
                "legs within 35 degrees of square",
                (
                    ("B  UR20 vertical", 17, True),
                    ("B  UR20 lean 15", 16, True),
                    ("B  UR20 lean 30", 15, True),
                    ("A  UR20 carry", 17, True),
                    ("B  SR-20iA", 14, False),
                    ("A  SR-20iA carry", 16, False),
                ),
            ),
            (
                "legs at any heading",
                (
                    ("B  UR20 vertical", 17, True),
                    ("B  UR20 lean 15", 14, True),
                    ("A  UR20 carry", 16, True),
                    ("B  SR-20iA", 9, False),
                    ("A  SR-20iA carry", 9, False),
                ),
            ),
        )
        full = 2.5
        panels = VGroup()
        for panel_index, (title, rows) in enumerate(sets):
            left = -6.85 if panel_index == 0 else 0.35
            name = line(title, size=ANNOT, color=INK).move_to([left, 2.45, 0], aligned_edge=LEFT)
            items = VGroup(name)
            for index, (label_text, score, six_axis_arm) in enumerate(rows):
                y = 1.75 - index * 0.66
                label_obj = figure(label_text, size=18, color=INK_2).move_to([left, y, 0], aligned_edge=LEFT)
                bar = Rectangle(
                    width=full * score / 20,
                    height=0.34,
                    fill_color=BLUE if six_axis_arm else INK_3,
                    fill_opacity=1,
                    stroke_width=0,
                )
                bar.move_to([left + 2.55, y, 0], aligned_edge=LEFT)
                value = figure(f"{score} / 20", size=18, color=INK).next_to(bar, RIGHT, buff=0.14)
                items.add(VGroup(label_obj, bar, value))
            panels.add(items)
        for items in panels:
            self.play(FadeIn(items[0]), run_time=0.5)
            self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.15) for r in items[1:]], lag_ratio=0.12), run_time=1.4)
        legend = (
            VGroup(
                Rectangle(width=0.3, height=0.2, fill_color=BLUE, fill_opacity=1, stroke_width=0),
                figure("six-axis, UR20", size=18, color=INK_2),
                Rectangle(width=0.3, height=0.2, fill_color=INK_3, fill_opacity=1, stroke_width=0),
                figure("SCARA, SR-20iA", size=18, color=INK_2),
                figure("A carries the leg, B turns it on the belt", size=18, color=INK_2),
            )
            .arrange(RIGHT, buff=0.22)
            .move_to([0, -2.05, 0])
        )
        legend[2].shift(RIGHT * 0.35)
        legend[3].shift(RIGHT * 0.35)
        legend[4].shift(RIGHT * 0.7)
        self.play(FadeIn(legend), run_time=0.7)
        self.wait(1.6)

        causes = (
            VGroup(
                line(
                    "The UR20's misses are mostly cut angles after release, at the rigid hold-down.",
                    size=ANNOT,
                    color=INK_2,
                ),
                line(
                    "10 of the SR-20iA's 11 misses at any heading are reach: 5 picks, 5 set-downs.",
                    size=ANNOT,
                    color=INK_2,
                ),
                line(
                    "A pass is a cut within 10 mm of the hock and 5 degrees of square, both assumed.",
                    size=ANNOT,
                    color=INK_3,
                ),
            )
            .arrange(DOWN, buff=0.16)
            .move_to([0, -3.05, 0])
        )
        self.play(LaggedStart(*[FadeIn(c) for c in causes], lag_ratio=0.3), run_time=1.6)
        self.wait(3.0)


class Transfer(Scene):
    """The same graph on a second product, and the check that stopped it."""

    def construct(self) -> None:
        """Swap the product under an unchanged chain, then run the gripper into its limit."""
        names = ["perceive", "grasp", "turn", "release", "judge"]
        nodes = VGroup()
        for text in names:
            frame = Rectangle(width=2.15, height=0.9, color=RULE, stroke_width=2)
            nodes.add(VGroup(frame, figure(text, size=ANNOT, color=INK).move_to(frame.get_center())))
        nodes.arrange(RIGHT, buff=0.52).shift(UP * 1.5)
        links = VGroup(
            *[
                Arrow(
                    nodes[i].get_right(),
                    nodes[i + 1].get_left(),
                    buff=0.06,
                    color=INK_3,
                    stroke_width=3,
                    max_tip_length_to_length_ratio=0.3,
                )
                for i in range(len(nodes) - 1)
            ]
        )
        heading = line("The second cell runs the same chain.", size=HEAD).to_edge(UP, buff=0.5)
        self.play(FadeIn(heading, shift=DOWN * 0.15), run_time=1.0)
        self.play(FadeIn(nodes), Create(links), run_time=1.4)

        # The authored moment: the product changes shape while the chain holds still.
        piece = leg(2.8).move_to([0, -0.9, 0])
        piece_name = line("pork leg", size=ANNOT, color=INK_2).next_to(piece, DOWN, buff=0.45)
        self.play(FadeIn(piece, shift=UP * 0.2), FadeIn(piece_name), run_time=1.0)
        self.wait(1.0)

        loin = Rectangle(width=4.16, height=0.95, fill_color=MEAT, fill_opacity=1, stroke_width=0)
        loin.move_to(piece.get_center())
        loin_name = line("loin", size=ANNOT, color=INK_2).move_to(piece_name.get_center())
        self.play(
            ReplacementTransform(piece, loin),
            ReplacementTransform(piece_name, loin_name),
            run_time=1.6,
            rate_func=EASE,
        )
        kept = line("The skills took new targets. The piece and the gripper changed.", size=BODY, color=BLUE).to_edge(
            DOWN, buff=0.55
        )
        self.play(FadeIn(kept, shift=UP * 0.15), run_time=1.0)
        self.wait(1.8)
        self.play(*[FadeOut(m) for m in (nodes, links, kept, heading, loin_name)], run_time=0.8)

        # The gripper decides the first run before the arm moves.
        self.play(loin.animate.move_to([0, -0.1, 0]).scale(1.25), run_time=1.0)
        width = Line(loin.get_left(), loin.get_right(), color=INK, stroke_width=2).shift(DOWN * 1.25)
        width_name = figure("164 to 211 mm across", size=BODY).next_to(width, DOWN, buff=0.22)
        self.play(Create(width, rate_func=EASE), FadeIn(width_name), run_time=1.0)

        # 180 mm of jaw against the widest 211 mm loin, to the same scale.
        grip = jaws(loin.width * 180 / 211, height=2.1).move_to(loin.get_center())
        span = Line(grip[0].get_center(), grip[1].get_center(), color=BLUE, stroke_width=2).shift(UP * 1.5)
        span_name = figure("the jaws open 180 mm", size=BODY, color=BLUE).next_to(span, UP, buff=0.22)
        self.play(FadeIn(grip), Create(span), FadeIn(span_name), run_time=1.1)
        self.wait(0.8)

        self.play(
            grip[0].animate.shift(RIGHT * 0.32),
            grip[1].animate.shift(LEFT * 0.32),
            run_time=0.5,
        )
        refused = figure("Refused, all 80 runs", size=HEAD, color=WARN).to_edge(DOWN, buff=0.5)
        self.play(FadeIn(refused, scale=1.15), run_time=0.9)
        self.wait(1.2)
        checked = line("The fit check caught it before the arm moved.", size=BODY, color=INK_2)
        checked.next_to(refused, UP, buff=0.3)
        self.play(FadeIn(checked), run_time=0.9)
        self.wait(1.6)
        self.play(
            *[FadeOut(m) for m in (loin, grip, span, span_name, width, width_name, refused, checked)], run_time=0.8
        )

        # With a gripper that fits.
        wider = VGroup(
            line("Run two: a wider jaw on the same skills.", size=BODY, color=INK_2),
            figure("20 of 20 on both arms, arriving near square", size=HEAD, color=BLUE),
            figure("4 and 10 of 20 at any heading", size=HEAD, color=WARN),
            line(
                "Past 40 degrees of turn the loin's ends hit the far rail. The fix is layout or planning.",
                size=ANNOT,
                color=INK_2,
            ),
            line("The wider jaw is a placeholder. Its force and mass are unverified.", size=ANNOT, color=INK_3),
        ).arrange(DOWN, buff=0.36)
        self.play(FadeIn(wider[0]), run_time=0.8)
        self.play(Write(wider[1]), run_time=1.3)
        self.play(Write(wider[2]), run_time=1.1)
        self.play(FadeIn(wider[3]), FadeIn(wider[4]), run_time=1.0)
        self.wait(2.6)
