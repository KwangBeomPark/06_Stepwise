"""Data models representing Stepwise macro entities (Section 6).

Uses standard dataclasses with zero heavy external dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class RecordedScreen:
    width: int = 1920
    height: int = 1080
    scale_percent: int = 100
    monitor_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RecordedScreen:
        if not data:
            return cls()
        return cls(
            width=int(data.get("width", 1920)),
            height=int(data.get("height", 1080)),
            scale_percent=int(data.get("scale_percent", 100)),
            monitor_count=int(data.get("monitor_count", 1)),
        )


@dataclass
class MacroSettings:
    default_wait_before: float = 0.2
    image_confidence: float = 0.95
    poll_interval: float = 0.25
    type_mode: Literal["paste", "keystrokes"] = "paste"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> MacroSettings:
        if not data:
            return cls()
        return cls(
            default_wait_before=float(data.get("default_wait_before", 0.2)),
            image_confidence=float(data.get("image_confidence", 0.95)),
            poll_interval=float(data.get("poll_interval", 0.25)),
            type_mode=data.get("type_mode", "paste"),
        )


@dataclass
class DataSourceConfig:
    type: Literal["xlsx", "csv"] = "xlsx"
    file_hint: str | None = None
    sheet: str | None = None
    header_row: int = 1
    encoding: str | None = None
    delimiter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DataSourceConfig | None:
        if not data:
            return None
        return cls(
            type=data.get("type", "xlsx"),
            file_hint=data.get("file_hint"),
            sheet=data.get("sheet"),
            header_row=int(data.get("header_row", 1)),
            encoding=data.get("encoding"),
            delimiter=data.get("delimiter"),
        )


@dataclass
class ImageCondition:
    image: str
    region: list[int] | None = None
    confidence: float | None = None
    timeout: float = 10.0
    after_found: float = 0.0
    stable_for: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "image": self.image,
            "region": self.region,
            "confidence": self.confidence,
            "timeout": self.timeout,
            "after_found": self.after_found,
        }
        if self.stable_for > 0:
            res["stable_for"] = self.stable_for
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ImageCondition | None:
        if not data or not data.get("image"):
            return None
        return cls(
            image=data["image"],
            region=data.get("region"),
            confidence=float(data["confidence"]) if data.get("confidence") is not None else None,
            timeout=float(data.get("timeout", 10.0)),
            after_found=float(data.get("after_found", 0.0)),
            stable_for=float(data.get("stable_for", 0.0)),
        )


@dataclass
class ActionItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = "click"
    enabled: bool = True
    note: str = ""
    wait_before: float | None = None
    guard: ImageCondition | None = None
    verify: ImageCondition | None = None

    # Click parameters
    x: int = 0
    y: int = 0
    button: Literal["left", "right", "middle"] = "left"
    clicks: int = 1

    # Image action parameters
    image: str | None = None
    region: list[int] | None = None
    confidence: float | None = None
    timeout: float = 10.0
    after_found: float = 0.0
    offset_x: int = 0
    offset_y: int = 0
    stable_for: float = 0.0
    appear_grace: float = 0.0
    after_gone: float = 0.0

    # Type text parameters
    text: str = ""
    mode: Literal["paste", "keystrokes"] = "paste"
    select_all_first: bool = False

    # Key parameters
    keys: str = ""
    repeat: int = 1

    # Wait parameters
    seconds: float = 1.0

    # Window bounds parameters (Window alignment / resize)
    window_title: str = ""
    window_x: int = 0
    window_y: int = 0
    window_width: int = 1280
    window_height: int = 800
    window_maximize: bool = False

    # Group container parameters
    name: str = ""
    collapsed: bool = False
    items: list[ActionItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "enabled": self.enabled,
        }
        if self.note:
            data["note"] = self.note
        if self.wait_before is not None:
            data["wait_before"] = self.wait_before
        if self.guard:
            data["guard"] = self.guard.to_dict()
        if self.verify:
            data["verify"] = self.verify.to_dict()

        if self.type == "click":
            data.update({"x": self.x, "y": self.y, "button": self.button, "clicks": self.clicks})
        elif self.type == "click_image":
            data.update(
                {
                    "image": self.image,
                    "region": self.region,
                    "confidence": self.confidence,
                    "timeout": self.timeout,
                    "offset_x": self.offset_x,
                    "offset_y": self.offset_y,
                    "button": self.button,
                    "clicks": self.clicks,
                    "after_found": self.after_found,
                }
            )
        elif self.type == "type_text":
            data.update(
                {"text": self.text, "mode": self.mode, "select_all_first": self.select_all_first}
            )
        elif self.type == "key":
            data.update({"keys": self.keys, "repeat": self.repeat})
        elif self.type == "wait":
            data.update({"seconds": self.seconds})
        elif self.type == "wait_image":
            data.update(
                {
                    "image": self.image,
                    "region": self.region,
                    "confidence": self.confidence,
                    "timeout": self.timeout,
                    "after_found": self.after_found,
                    "stable_for": self.stable_for,
                }
            )
        elif self.type == "wait_image_gone":
            data.update(
                {
                    "image": self.image,
                    "region": self.region,
                    "confidence": self.confidence,
                    "timeout": self.timeout,
                    "appear_grace": self.appear_grace,
                    "after_gone": self.after_gone,
                }
            )
        elif self.type == "window_set_bounds":
            data.update(
                {
                    "window_title": self.window_title,
                    "window_x": self.window_x,
                    "window_y": self.window_y,
                    "window_width": self.window_width,
                    "window_height": self.window_height,
                    "window_maximize": self.window_maximize,
                }
            )
        elif self.type == "group":
            data.update(
                {
                    "name": self.name,
                    "collapsed": self.collapsed,
                    "items": [it.to_dict() for it in self.items],
                }
            )

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionItem:
        act = cls(
            id=str(data.get("id") or str(uuid.uuid4())[:8]),
            type=str(data.get("type", "click")),
            enabled=bool(data.get("enabled", True)),
            note=str(data.get("note", "")),
            wait_before=float(data["wait_before"]) if data.get("wait_before") is not None else None,
            guard=ImageCondition.from_dict(data.get("guard")),
            verify=ImageCondition.from_dict(data.get("verify")),
        )

        act.x = int(data.get("x", 0))
        act.y = int(data.get("y", 0))
        act.button = data.get("button", "left")
        act.clicks = int(data.get("clicks", 1))

        act.image = data.get("image")
        act.region = data.get("region")
        act.confidence = float(data["confidence"]) if data.get("confidence") is not None else None
        act.timeout = float(data.get("timeout", 10.0))
        act.after_found = float(data.get("after_found", 0.0))
        act.offset_x = int(data.get("offset_x", 0))
        act.offset_y = int(data.get("offset_y", 0))
        act.stable_for = float(data.get("stable_for", 0.0))
        act.appear_grace = float(data.get("appear_grace", 0.0))
        act.after_gone = float(data.get("after_gone", 0.0))

        act.text = str(data.get("text", ""))
        act.mode = data.get("mode", "paste")
        act.select_all_first = bool(data.get("select_all_first", False))

        act.keys = str(data.get("keys", ""))
        act.repeat = int(data.get("repeat", 1))
        act.seconds = float(data.get("seconds", 1.0))

        act.window_title = str(data.get("window_title", ""))
        act.window_x = int(data.get("window_x", 0))
        act.window_y = int(data.get("window_y", 0))
        act.window_width = int(data.get("window_width", 1280))
        act.window_height = int(data.get("window_height", 800))
        act.window_maximize = bool(data.get("window_maximize", False))

        act.name = str(data.get("name", ""))
        act.collapsed = bool(data.get("collapsed", False))
        act.items = [ActionItem.from_dict(item_data) for item_data in (data.get("items") or [])]

        return act


@dataclass(frozen=True)
class ActionLocation:
    section: str
    parent: ActionItem | None
    items: list[ActionItem]
    index: int


@dataclass
class Macro:
    schema_version: int = 1
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Macro"
    description: str = ""
    created_by: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    recorded_screen: RecordedScreen = field(default_factory=RecordedScreen)
    settings: MacroSettings = field(default_factory=MacroSettings)
    data_source: DataSourceConfig | None = None
    setup: list[ActionItem] = field(default_factory=list)
    per_row: list[ActionItem] = field(default_factory=list)
    cleanup: list[ActionItem] = field(default_factory=list)

    def find_action_location(self, action: ActionItem) -> ActionLocation | None:
        """Find the owning list at any group depth, matching by object identity."""

        def find(
            section: str, items: list[ActionItem], parent: ActionItem | None = None
        ) -> ActionLocation | None:
            for index, item in enumerate(items):
                if item is action:
                    return ActionLocation(section, parent, items, index)
                if item.type == "group":
                    location = find(section, item.items, item)
                    if location is not None:
                        return location
            return None

        for section in ("setup", "per_row", "cleanup"):
            location = find(section, getattr(self, section))
            if location is not None:
                return location
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "recorded_screen": self.recorded_screen.to_dict(),
            "settings": self.settings.to_dict(),
            "data_source": self.data_source.to_dict() if self.data_source else None,
            "setup": [item.to_dict() for item in self.setup],
            "per_row": [item.to_dict() for item in self.per_row],
            "cleanup": [item.to_dict() for item in self.cleanup],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Macro:
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            id=str(data.get("id") or str(uuid.uuid4())),
            name=str(data.get("name", "Unnamed Macro")),
            description=str(data.get("description", "")),
            created_by=str(data.get("created_by", "")),
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            modified_at=str(data.get("modified_at", datetime.now().isoformat())),
            recorded_screen=RecordedScreen.from_dict(data.get("recorded_screen")),
            settings=MacroSettings.from_dict(data.get("settings")),
            data_source=DataSourceConfig.from_dict(data.get("data_source")),
            setup=[ActionItem.from_dict(it) for it in (data.get("setup") or [])],
            per_row=[ActionItem.from_dict(it) for it in (data.get("per_row") or [])],
            cleanup=[ActionItem.from_dict(it) for it in (data.get("cleanup") or [])],
        )
