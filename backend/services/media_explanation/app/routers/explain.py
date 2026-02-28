import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response

from ..config import Settings, get_settings
from ..minimax import (
    _build_script,
    generate_audio,
    generate_explanation_script_and_fragments,
    generate_flashcards,
    generate_video_with_audio_and_fragments,
)
from ..schemas import ExplainRequest, FlashcardsResponse

router = APIRouter(tags=["explain"])
logger = logging.getLogger("media_explanation")


@router.post("/explain/generate")
async def explain_generate(
    payload: ExplainRequest,
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Generate an explanatory video, audio, or flashcards for a trust-score result.

    - video: returns video/mp4 binary
    - audio: returns audio/mpeg binary
    - flashcards: returns JSON {"flashcards": [{front, back}, ...]}
    """
    if not settings.minimax_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Minimax API key is not configured (MEDIA_EXPLANATION_MINIMAX_API_KEY not set)",
        )

    trust_score_raw = payload.response.get("trust_score")
    trust_score_int = int(trust_score_raw) if trust_score_raw is not None else None
    logger.info(
        "explain/generate: type=%s trust_score=%s",
        payload.explanation_type,
        trust_score_raw,
    )

    if payload.explanation_type == "video":
        logger.info("explain/video: video explanation requested")
        script: str
        fragment_prompts: list[str]
        try:
            script, fragment_prompts = await generate_explanation_script_and_fragments(
                payload.response, payload.user_prompt, settings
            )
            logger.info(
                "explain/video: using LLM script and %s fragment prompts",
                len(fragment_prompts),
            )
        except (ValueError, asyncio.TimeoutError) as e:
            logger.warning(
                "explain/video: LLM script/fragments failed (%s), using fallback script and static frame",
                e,
            )
            script = _build_script(payload.response, payload.user_prompt)
            fragment_prompts = []
        try:
            logger.info("explain/video: script ready words=%s chars=%s", len(script.split()), len(script))
            video_bytes = await generate_video_with_audio_and_fragments(
                script, fragment_prompts, settings, trust_score=trust_score_int
            )
        except asyncio.TimeoutError as e:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Video generation timed out: {e}",
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Video generation failed: {e}",
            ) from e
        except Exception as e:
            logger.exception("Unexpected error in video generation: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Video generation error: {e}",
            ) from e

        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers={"Content-Disposition": 'attachment; filename="explanation.mp4"'},
        )

    elif payload.explanation_type == "audio":
        # Use the same template-built script as flashcards so the script is always available.
        try:
            script = _build_script(payload.response, payload.user_prompt)
            logger.info("explain/generate audio: script ready words=%s chars=%s", len(script.split()), len(script))
            audio_bytes = await generate_audio(script, settings)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Audio generation failed: {e}",
            ) from e
        except Exception as e:
            logger.exception("Unexpected error in audio generation: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Audio generation error: {e}",
            ) from e

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'attachment; filename="explanation.mp3"'},
        )

    else:  # flashcards — keep template-built script for structured fact extraction
        script = _build_script(payload.response, payload.user_prompt)
        logger.info("explain/generate flashcards: script ready words=%s", len(script.split()))
        try:
            cards = await generate_flashcards(script, payload.user_prompt, settings)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flashcards generation failed: {e}",
            ) from e
        except Exception as e:
            logger.exception("Unexpected error in flashcards generation: %s", e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Flashcards generation error: {e}",
            ) from e

        return JSONResponse(content={"flashcards": cards})
