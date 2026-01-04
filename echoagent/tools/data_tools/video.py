"""Video question answering tool for analyzing video content."""

from typing import Union, Dict, Any
import os
import tempfile
from pathlib import Path
from agents import function_tool
from agents.run_context import RunContextWrapper
from echoagent.utils.data_store import DataStore
from loguru import logger
import requests


@function_tool
async def video_qa(
    ctx: RunContextWrapper[DataStore],
    video_url: str,
    question: str
) -> Union[str, Dict[str, Any]]:
    """Asks a question about a video using AI vision capabilities.

    This tool uses Google's Gemini model to analyze video content and answer
    questions about it. The video can be provided as either a local file path
    or a URL.

    Args:
        ctx: Pipeline context wrapper for accessing the data store
        video_url: Path to the video file or URL. Supports local files and HTTP(S) URLs.
        question: The question to ask about the video content.

    Returns:
        String containing the answer to the question about the video,
        or error message if the analysis fails.

    Examples:
        - "What objects are visible in this video?"
        - "Describe the main actions happening in the video"
        - "How many people appear in this video?"
    """
    try:
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "Error: GEMINI_API_KEY environment variable not set. Please set it to use video_qa."

        client, error = _get_genai_client(api_key)
        if error:
            return error

        # Prepare the video input
        temp_path: Path | None = None
        if video_url.startswith("http://") or video_url.startswith("https://"):
            # Use URL directly
            logger.info(f"Analyzing video from URL: {video_url}")
            temp_path = _download_to_temp_file(video_url)
            upload_path = temp_path
        else:
            # Handle local file path
            video_path = Path(video_url)
            if not video_path.exists():
                return f"Error: Video file not found: {video_url}"

            logger.info(f"Uploading and analyzing local video: {video_path}")
            upload_path = video_path.resolve()

        # Generate response
        logger.info(f"Asking question: {question}")
        response = None
        try:
            video_file = client.files.upload(file=str(upload_path))
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=[question, video_file],
            )
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass

        # Extract and return the text response
        answer = response.text if response is not None else ""
        logger.info(f"Video QA response received: {answer[:100]}...")

        # Store the result in context if needed
        data_store = ctx.context
        if data_store is not None:
            cache_key = f"video_qa:{video_url}:{question}"
            data_store.set(
                cache_key,
                answer,
                data_type="text",
                metadata={
                    "video_url": video_url,
                    "question": question,
                }
            )
            logger.info(f"Cached video QA result with key: {cache_key}")

        return answer

    except Exception as e:
        error_msg = f"Error analyzing video: {str(e)}"
        logger.error(error_msg)
        return error_msg


def _get_genai_client(api_key: str):
    try:
        from google import genai
    except Exception:
        return None, "Error: google-genai is not installed. Please install google-genai to use video_qa."
    return genai.Client(api_key=api_key), None


def _download_to_temp_file(url: str) -> Path:
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    suffix = Path(url).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
        return Path(handle.name)
