from fastapi import APIRouter
from fastapi.responses import RedirectResponse, JSONResponse
from loguru import logger

router = APIRouter()


# TODO replace  BooleanResponse, StringResponse with JSONResp (change in the Plugin!)

@router.get("/", tags=["general"], description="Redirection to /docs")
async def root_to_docs():
    logger.info("GET request on / -> redirecting to /docs")
    return RedirectResponse("/docs")


@router.get("/heartbeat", tags=["general"], description="Heartbeat check")
async def heartbeat():
    logger.info("GET request on /heartbeat")
    return JSONResponse(content=True)
