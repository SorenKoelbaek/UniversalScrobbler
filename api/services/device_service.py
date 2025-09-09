from sqlmodel import select
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Device, User, PlaybackSession
from uuid import UUID
from fastapi import HTTPException
from typing import List
from pydantic import parse_obj_as
import logging


logger = logging.getLogger(__name__)

class DeviceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def switch_active_device(self, user_uuid: UUID, device_uuid: UUID) -> PlaybackSession:
        """
        Set the active playback device for a user.
        """
        result = await self.db.execute(
            select(PlaybackSession).where(PlaybackSession.user_uuid == user_uuid)
        )
        session = result.scalars().first()
        if not session:
            session = PlaybackSession(user_uuid=user_uuid)

        session.active_device_uuid = device_uuid
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_or_create_device(
        self, user_uuid: UUID, device_id: str, device_name: str
    ) -> Device:
        """Get existing device for user or create a new one.
        If device exists but name has changed → update it.
        """
        if device_id is None:
            logger.error(f"_get_or_create_session called with NULL device_id for user={user_uuid}")
        logger.info(device_name+" "+device_id)
        # Look up by device_id (preferred stable key)
        stmt = select(Device).where(
            Device.user_uuid == user_uuid,
            Device.device_id == device_id,
        )
        result = await self.db.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            # 🚫 no fallback by name, always create new device
            device = Device(
                user_uuid=user_uuid,
                device_id=device_id,
                device_name=device_name,
            )
            self.db.add(device)
            await self.db.flush()
            await self.db.refresh(device)

        if not device:
            # Create new device
            device = Device(
                user_uuid=user_uuid,
                device_id=device_id,
                device_name=device_name,
            )
            self.db.add(device)
            await self.db.flush()
            await self.db.refresh(device)
        else:
            # Update name if changed
            if device.device_name != device_name:
                device.device_name = device_name
                self.db.add(device)
                await self.db.flush()

        return device
