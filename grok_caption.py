"""xAI Grok Vision caption generation for LoRA datasets."""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.x.ai/v1/chat/completions"
API_TIMEOUT = 3600

MODEL_REASONING = "grok-4.20-0309-reasoning"
MODEL_NON_REASONING = "grok-4.20-0309-non-reasoning"

MAX_CAPTION_RETRIES = 3
RETRY_BASE_DELAY_SEC = 2.0

PRICE_INPUT_PER_MILLION = 1.25
PRICE_OUTPUT_PER_MILLION = 2.50
EST_PROMPT_TOKENS = 250
EST_OUTPUT_TOKENS = 120

GROK_VISION_DEFAULT_MAX_LONG_EDGE = 1536
GROK_VISION_JPEG_QUALITY = 88

GROK_VISION_MAX_EDGE_OPTIONS = [
    (1024, "1024 px — save tokens"),
    (1536, "1536 px — balanced"),
    (2048, "2048 px — max detail"),
]

_EST_IMAGE_TOKENS_BY_MAX_EDGE = {
    1024: 500,
    1536: 750,
    2048: 1100,
}

CAPTION_FOCUS_OPTIONS = [
    ("mixed", "Mixed (full description)"),
    ("character", "Character"),
    ("style", "Style / art medium"),
    ("camera_angle", "Camera angle"),
    ("lighting", "Lighting"),
    ("background", "Background / environment"),
    ("clothing", "Clothing / outfit"),
]

TRAINING_TARGET_OPTIONS = [
    ("flux", "Flux"),
    ("flux_krea2", "Krea-2"),
    ("sdxl", "SDXL"),
    ("sd15", "SD 1.5"),
    ("pony", "Pony / Danbooru-style"),
]

FLUX_KREA2_KEY = "flux_krea2"

KREA2_LORA_TYPE_OPTIONS = [
    ("character", "Character LoRA"),
    ("style", "Style LoRA"),
    ("concept", "Concept LoRA"),
    ("lighting", "Lighting LoRA"),
]

_KREA2_INSTRUCTIONS = {
    "character": (
        "Character LoRA rules — be extremely minimalist.\n"
        "PRIORITY #1: Camera angle is most important. Describe it clearly and precisely "
        "(e.g. front view, low angle side view, back three quarter view, "
        "extreme low angle back view).\n"
        "PRIORITY #2: Mention pose ONLY when it is obvious and relevant. Be conservative "
        "and accurate — do not guess; never say standing if the subject is kneeling.\n"
        "PRIORITY #3: Mention lighting ONLY when it is very unusual or distinctive. "
        "In most images, omit lighting entirely.\n"
        "LENGTH: Keep captions short — ideally 5 to 10 words (excluding any trigger word "
        "the user adds separately).\n"
        "NEVER describe: face, body, proportions, robotic parts, clothing, hair, "
        "expression, identity, or any physical character details."
    ),
    "style": (
        "Style LoRA rules: Describe visual style, lighting, atmosphere, and image quality. "
        "Emphasize artistic look and rendering rather than who or what is in the scene."
    ),
    "concept": (
        "Concept LoRA rules: Be specific and clear about the concept being taught. "
        "Describe what makes this concept visually distinct in the image."
    ),
    "lighting": (
        "Lighting LoRA rules: Focus on light type, direction, shadows, highlights, "
        "and atmospheric lighting mood."
    ),
}

_KREA2_HINTS = {
    "character": "Minimal: camera angle first. Pose only if obvious. Skip lighting unless unusual.",
    "style": "Visual style, lighting, atmosphere & image quality.",
    "concept": "Be specific about the concept being taught.",
    "lighting": "Light type, direction, shadows & atmospheric mood.",
}

_FOCUS_INSTRUCTIONS = {
    "character": (
        "Focus on the subject: appearance, face, hair, expression, pose, body, "
        "and distinguishing features. Do not describe background unless essential."
    ),
    "style": (
        "Focus on artistic style, medium, rendering technique, color palette, "
        "mood, and visual aesthetics."
    ),
    "camera_angle": (
        "Focus on camera angle, framing, shot type, perspective, depth of field, "
        "and composition."
    ),
    "lighting": (
        "Focus on lighting setup, direction, shadows, highlights, time of day, "
        "and atmosphere created by light."
    ),
    "background": (
        "Focus on environment, setting, background elements, location, and context."
    ),
    "clothing": (
        "Focus on outfit, clothing details, accessories, fabrics, colors, and fashion."
    ),
    "mixed": (
        "Describe the image comprehensively: subject, style, composition, lighting, "
        "and environment as needed for ML training."
    ),
}

_TARGET_INSTRUCTIONS = {
    "flux": (
        "Write a natural-language caption in flowing prose. Use commas between phrases. "
        "No bullet points. No quotes. Single line only."
    ),
    "sdxl": (
        "Write a detailed comma-separated tag list suitable for SDXL LoRA training. "
        "Use lowercase tags, no full sentences. Single line only."
    ),
    "sd15": (
        "Write a concise comma-separated tag caption for Stable Diffusion 1.5 LoRA. "
        "Short descriptive tags only. Single line only."
    ),
    "pony": (
        "Write a booru-style comma-separated tag caption (like danbooru/e621). "
        "Use underscore_tags where appropriate. Single line only."
    ),
}


class GrokCaptionError(Exception):
    pass


def model_from_mode(mode: str) -> str:
    if mode == "non_reasoning":
        return MODEL_NON_REASONING
    return MODEL_REASONING


def tokens_to_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1_000_000 * PRICE_INPUT_PER_MILLION
        + completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_MILLION
    )


def normalize_max_long_edge(value: int | str | None) -> int:
    try:
        edge = int(value)
    except (TypeError, ValueError):
        return GROK_VISION_DEFAULT_MAX_LONG_EDGE
    allowed = {option[0] for option in GROK_VISION_MAX_EDGE_OPTIONS}
    if edge not in allowed:
        return GROK_VISION_DEFAULT_MAX_LONG_EDGE
    return edge


def label_for_max_long_edge(edge: int) -> str:
    edge = normalize_max_long_edge(edge)
    for option_edge, label in GROK_VISION_MAX_EDGE_OPTIONS:
        if option_edge == edge:
            return label
    return GROK_VISION_MAX_EDGE_OPTIONS[1][1]


def max_long_edge_from_label(label: str) -> int:
    for edge, option_label in GROK_VISION_MAX_EDGE_OPTIONS:
        if option_label == label:
            return edge
    return GROK_VISION_DEFAULT_MAX_LONG_EDGE


def estimate_image_tokens(max_long_edge: int | str | None = None) -> int:
    edge = normalize_max_long_edge(max_long_edge)
    return _EST_IMAGE_TOKENS_BY_MAX_EDGE.get(edge, _EST_IMAGE_TOKENS_BY_MAX_EDGE[1536])


def estimate_batch_cost(
    image_count: int,
    max_long_edge: int | str | None = None,
) -> dict:
    input_per_image = EST_PROMPT_TOKENS + estimate_image_tokens(max_long_edge)
    output_per_image = EST_OUTPUT_TOKENS
    total_input = input_per_image * image_count
    total_output = output_per_image * image_count
    return {
        "images": image_count,
        "estimated_input_tokens": total_input,
        "estimated_output_tokens": total_output,
        "estimated_total_tokens": total_input + total_output,
        "estimated_cost_usd": tokens_to_cost_usd(total_input, total_output),
    }


def format_cost_estimate(estimate: dict) -> str:
    return (
        f"Est. cost: ~${estimate['estimated_cost_usd']:.2f} USD "
        f"({estimate['images']} images, "
        f"~{estimate['estimated_total_tokens']:,} tokens)"
    )


def format_actual_cost(prompt_tokens: int, completion_tokens: int) -> str:
    total = prompt_tokens + completion_tokens
    cost = tokens_to_cost_usd(prompt_tokens, completion_tokens)
    return f"Actual cost: ~${cost:.3f} USD ({total:,} tokens)"


def _merge_usage(total: dict, usage: dict) -> dict:
    merged = dict(total)
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        merged[key] = merged.get(key, 0) + int(usage.get(key, 0) or 0)
    return merged


def _is_non_retryable(error_message: str) -> bool:
    lowered = error_message.lower()
    markers = (
        "too large",
        "invalid api",
        "incorrect api",
        "unauthorized",
        "http 401",
        "http 403",
        "invalid api key",
    )
    return any(marker in lowered for marker in markers)


def is_flux_krea2_target(target_key: str) -> bool:
    return target_key == FLUX_KREA2_KEY


def krea2_hint_for_type(lora_type_key: str) -> str:
    return _KREA2_HINTS.get(lora_type_key, _KREA2_HINTS["character"])


def build_krea2_caption_prompt(lora_type_key: str) -> str:
    type_labels = {key: label for key, label in KREA2_LORA_TYPE_OPTIONS}
    lora_label = type_labels.get(lora_type_key, "Character LoRA")
    rules = _KREA2_INSTRUCTIONS.get(lora_type_key, _KREA2_INSTRUCTIONS["character"])

    if lora_type_key == "character":
        return (
            "Act as an expert in captions for Character LoRAs trained in Krea-2.\n"
            f"Training type: {lora_label}.\n"
            f"{rules}\n"
            "Good examples:\n"
            "- front view\n"
            "- low angle side view\n"
            "- back three quarter view\n"
            "- extreme low angle back view\n"
            "Bad examples (too long, wrong priorities):\n"
            "- front view, upright kneeling pose, bright overhead lighting with blue accents\n"
            "- low angle side view, kneeling on platform, dramatic blue neon lighting "
            "with overhead highlights\n"
            "Format: natural language with commas between phrases. Single line only.\n"
            "Rules: output ONLY the caption text (no trigger word — the app adds it). "
            "No preamble, no markdown, no quotes. Do not mention that you are describing an image."
        )

    return (
        "Act as an expert in captions for LoRAs in Krea-2.\n"
        f"Training type: {lora_label}.\n"
        f"{rules}\n"
        "Keep captions clear, natural, and moderate length. "
        "Adapt the level of detail to the LoRA objective.\n"
        "Use natural language with commas between phrases. Single line only.\n"
        "Rules: output ONLY the caption text. No preamble, no markdown, no quotes. "
        "Do not mention that you are describing an image."
    )


def build_caption_prompt(
    focus_key: str, target_key: str, krea2_lora_type: str = "character"
) -> str:
    if is_flux_krea2_target(target_key):
        return build_krea2_caption_prompt(krea2_lora_type)

    focus = _FOCUS_INSTRUCTIONS.get(focus_key, _FOCUS_INSTRUCTIONS["mixed"])
    target = _TARGET_INSTRUCTIONS.get(target_key, _TARGET_INSTRUCTIONS["flux"])
    return (
        "You are an expert at writing image captions for AI model training datasets.\n"
        f"Caption focus: {focus}\n"
        f"Output format: {target}\n"
        "Rules: output ONLY the caption text. No preamble, no markdown, no quotes. "
        "Do not mention that you are describing an image."
    )


def _prepare_vision_image_bytes(
    path: Path,
    max_long_edge: int | str | None = None,
) -> bytes:
    """Downscale if needed and encode as JPEG for Grok Vision (token-efficient)."""
    max_edge = normalize_max_long_edge(max_long_edge)
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise GrokCaptionError(
            "Pillow is required for Grok Vision captioning. "
            "Run: pip install pillow"
        ) from exc

    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        else:
            img = img.convert("RGB")

        width, height = img.size
        long_edge = max(width, height)
        if long_edge > max_edge:
            scale = max_edge / long_edge
            new_width = max(1, round(width * scale))
            new_height = max(1, round(height * scale))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(
            buffer,
            format="JPEG",
            quality=GROK_VISION_JPEG_QUALITY,
            optimize=True,
        )
        return buffer.getvalue()


def image_to_data_url(
    path: Path,
    max_long_edge: int | str | None = None,
) -> str:
    raw = _prepare_vision_image_bytes(path, max_long_edge=max_long_edge)
    if len(raw) > 20 * 1024 * 1024:
        raise GrokCaptionError(f"Image too large after resize (max 20 MiB): {path.name}")
    return f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}"


def _parse_response_body(body: str) -> tuple[str, dict]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise GrokCaptionError(f"Invalid API response: {body[:300]}") from exc

    if "error" in data:
        message = data["error"]
        if isinstance(message, dict):
            message = message.get("message", str(message))
        raise GrokCaptionError(str(message))

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GrokCaptionError(f"Unexpected API response shape: {body[:300]}") from exc

    if not isinstance(content, str) or not content.strip():
        raise GrokCaptionError("API returned an empty caption")

    usage = data.get("usage") or {}
    return " ".join(content.strip().split()), usage


def api_chat_completion(api_key: str, model: str, messages: list[dict]) -> tuple[str, dict]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GrokCaptionError(f"HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise GrokCaptionError(f"Network error: {exc.reason}") from exc

    return _parse_response_body(body)


def test_connection(api_key: str, model_mode: str) -> str:
    model = model_from_mode(model_mode)
    reply, _usage = api_chat_completion(
        api_key,
        model,
        [{"role": "user", "content": "Reply with exactly: OK"}],
    )
    return reply


def generate_caption(
    api_key: str,
    model_mode: str,
    image_path: Path,
    focus_key: str,
    target_key: str,
    krea2_lora_type: str = "character",
    max_long_edge: int | str | None = None,
) -> tuple[str, dict]:
    model = model_from_mode(model_mode)
    data_url = image_to_data_url(image_path, max_long_edge=max_long_edge)
    system_prompt = build_caption_prompt(focus_key, target_key, krea2_lora_type)
    if is_flux_krea2_target(target_key) and krea2_lora_type == "character":
        user_text = (
            "Write a minimal Character LoRA caption. Camera angle is the top priority. "
            "Omit lighting unless it is very unusual. Be accurate about pose."
        )
    else:
        user_text = "Write the training caption for this image."

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url, "detail": "high"},
                },
                {
                    "type": "text",
                    "text": user_text,
                },
            ],
        },
    ]
    return api_chat_completion(api_key, model, messages)


def generate_caption_with_retries(
    api_key: str,
    model_mode: str,
    image_path: Path,
    focus_key: str,
    target_key: str,
    krea2_lora_type: str = "character",
    max_long_edge: int | str | None = None,
) -> tuple[str, dict, int]:
    last_error: Exception | None = None
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for attempt in range(1, MAX_CAPTION_RETRIES + 1):
        try:
            caption, usage = generate_caption(
                api_key,
                model_mode,
                image_path,
                focus_key,
                target_key,
                krea2_lora_type,
                max_long_edge,
            )
            usage_total = _merge_usage(usage_total, usage)
            return caption, usage_total, attempt
        except GrokCaptionError as exc:
            last_error = exc
            if _is_non_retryable(str(exc)):
                raise
            if attempt < MAX_CAPTION_RETRIES:
                time.sleep(RETRY_BASE_DELAY_SEC * attempt)

    if last_error is not None:
        raise last_error
    raise GrokCaptionError(f"Failed to caption {image_path.name}")


def apply_trigger_prefix(caption: str, trigger_word: str) -> str:
    trigger = trigger_word.strip()
    if not trigger:
        return caption
    prefix = f"{trigger}, "
    lower_caption = caption.lower()
    lower_trigger = trigger.lower()
    if lower_caption.startswith(lower_trigger):
        return caption
    return f"{prefix}{caption}"