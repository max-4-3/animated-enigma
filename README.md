# Scraper & Downloaders

Currently it only _Supports_:

- [XNXX](https://xnxx.health/)
- [OkXxx](https://okxxx2.com/)
- [Pornhub](https://www.pornhub.com)

Video Data Struct ( Roufghly ):

```json
{
    "title": "Title of the video",
    "url": "Url of the video's page",
    "thumbnail": "Thumbnail Url",
    "media": {
        ...
        "width*height": {
            "name": "idk",
            "url": "The Link to the media"
        }
        ...
    },
    ...
}
```
