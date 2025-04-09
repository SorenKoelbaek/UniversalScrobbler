from sqlmodel import select
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from models.sqlmodels import Device, User
from uuid import UUID
from fastapi import HTTPException
from typing import List
from pydantic import parse_obj_as

class DeviceService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_or_create_device(self, user: User, device_id: str, device_name: str, ) -> Device:
        result = await self.db.execute(select(Device).where(
            Device.user_uuid == user.user_uuid,
            Device.device_id == device_id))
        device = result.scalar_one_or_none()
        if not device:
            device = Device(
                user_uuid=user.user_uuid,
                device_id=device_id,
                device_name=device_name,
            )
            self.db.add(device)
            await self.db.commit()
            await self.db.refresh(device)
        return device