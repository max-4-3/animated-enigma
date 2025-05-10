from pydantic import BaseModel, Field
from uuid import uuid4
from typing import List

class ExternalLink(BaseModel):
    name: str = Field(default="N/A", description="External site/service name")
    url: str = Field(default="N/A", description="External site URL")
    extras: dict = Field(default_factory=dict, description="Extra info related to this link as a dict")

class Tag(ExternalLink):
    pass

class Thumbnail(BaseModel):
    url: str = Field(..., pattern=r'^https?://.*', description="Thumbnail image URL")

class VideoLinks(BaseModel):
    title: str = Field(..., description="The Title of the links (e.g. Socials, etc)")
    links: List[ExternalLink] = Field(default_factory=[])

class Metadata(BaseModel):
    views: int = Field(default=0, description="Video's views as an integer")
    duration: int = Field(default=0, description="Video's duration in seconds")
    upload_date: str = Field(default="Now", description="Video's upload date in string format")
    extras: dict = Field(default_factory=dict, description="Extra related video info as a dict")

class ThumbVideo(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, description="Unique video ID")
    title: str = Field(default="No Title Provided!", description="Short video title")
    url: str = Field(..., pattern=r'^https?://.*', description="Video's page URL")
    thumbnail: Thumbnail
    metadata: Metadata
    links: list[VideoLinks] = Field(default_factory=list, description='Any Links related to this video thumb')

class MediaItem(BaseModel):
    idx: int = Field(default=1, description="Media index/sequence number")
    url: str = Field(..., pattern=r'^https://.*', description="Direct media stream URL")
    resolution: str = Field(default='0p', description="Media resolution (e.g., 1080p)")
    framerate: str = Field(default='60fps', description="Media framerate")
    bandwidth: str = Field(default='0kb/s', description="Estimated bandwidth usage")

class Media(BaseModel):
    base_url: str = Field(..., description="The index.m3u8 url")
    items: List[MediaItem] = Field(default_factory=list, description="The media items that holds the media!")

class Recommendations(BaseModel):
    title: str = Field(default="Recommended")
    contents: List[ThumbVideo] = Field(default_factory=list)

class Video(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, description="Unique video ID")
    title: str = Field(default="Untitled Video", description="Full video title")
    url: str = Field(..., pattern=r'^https?://.*', description="Video's page URL")
    metadata: Metadata
    thumbnail: Thumbnail
    media: Media
    tags: List[Tag | ExternalLink] = Field(default_factory=list)
    links: List[VideoLinks]
    recommendations: List[Recommendations] = Field(default_factory=list)
    extras: dict = Field(default_factory=dict, description="Extra info relevent to the video")
