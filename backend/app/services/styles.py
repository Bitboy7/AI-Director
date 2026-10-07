from dataclasses import dataclass


@dataclass(frozen=True)
class StyleDefinition:
    id: str
    label: str
    prompt: str


STYLES: tuple[StyleDefinition, ...] = (
    StyleDefinition(
        id="anime",
        label="Animado",
        prompt=(
            "anime style, cel-shaded 2D animation, clean confident line art, vibrant "
            "saturated palette, expressive characters, dynamic poses, detailed painted "
            "backgrounds, cinematic lighting, high quality key visual"
        ),
    ),
    StyleDefinition(
        id="cinematic",
        label="Cinemático",
        prompt=(
            "cinematic photorealistic film still, shot on 35mm, shallow depth of field, "
            "dramatic volumetric lighting, subtle film grain, professional color grading, "
            "high dynamic range, movie-quality detail"
        ),
    ),
    StyleDefinition(
        id="cyberpunk",
        label="Cyberpunk",
        prompt=(
            "cyberpunk aesthetic, neon-drenched futuristic city, rain-slicked reflective "
            "streets, holographic signage, teal and magenta palette, moody high-contrast "
            "atmosphere, cinematic haze"
        ),
    ),
    StyleDefinition(
        id="realistic",
        label="Realista",
        prompt=(
            "photorealistic, natural lighting, lifelike skin texture and materials, "
            "documentary realism, true-to-life colors, sharp focus, ultra-detailed, "
            "physically based rendering"
        ),
    ),
    StyleDefinition(
        id="3d",
        label="Animación 3D",
        prompt=(
            "3D animated feature film style, Pixar-like appeal, soft global illumination, "
            "stylized appealing characters, subsurface scattering, vibrant yet natural "
            "palette, cinematic depth of field"
        ),
    ),
    StyleDefinition(
        id="comic",
        label="Cómic",
        prompt=(
            "western comic book illustration, bold ink outlines, halftone dot shading, "
            "dramatic panel composition, saturated primary colors, dynamic perspective"
        ),
    ),
    StyleDefinition(
        id="noir",
        label="Cine negro",
        prompt=(
            "film noir, high-contrast black and white, hard directional shadows, venetian "
            "blind light patterns, smoky atmosphere, 1940s mood, moody chiaroscuro"
        ),
    ),
    StyleDefinition(
        id="watercolor",
        label="Acuarela",
        prompt=(
            "watercolor storybook illustration, soft translucent washes, textured "
            "cold-press paper, pastel palette, hand-painted, delicate linework, whimsical"
        ),
    ),
    StyleDefinition(
        id="retro",
        label="Retro VHS",
        prompt=(
            "1980s retro VHS aesthetic, chromatic aberration, scanlines, synthwave neon "
            "palette, glowing grids, analog grain and tracking artifacts, nostalgic"
        ),
    ),
)

_BY_ID = {style.id: style for style in STYLES}


def list_styles() -> list[StyleDefinition]:
    return list(STYLES)


def style_prompt(style: str | None) -> str:
    if not style:
        return ""
    definition = _BY_ID.get(style)
    return definition.prompt if definition else style
