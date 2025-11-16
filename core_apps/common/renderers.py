import json
from typing import Union, Any, Optional

from django.utils.translation import gettext_lazy as _
from rest_framework.renderers import JSONRenderer


class GenericJSONRenderer(JSONRenderer):
    charset = "utf-8"
    object_label = "object"

    def render(
        self,
        data: Any,
        accepted_media_type: Optional[str] = None,
        renderer_context: Optional[str] = None,
    ) -> Union[bytes, str]:
        renderer_context = renderer_context or {}

        response = renderer_context.get("response")
        view = renderer_context.get("view")

        if not response:
            raise ValueError(_("Response is required in the renderer context"))

        status_code = response.status_code

        object_label = getattr(view, "object_label", self.object_label)

        if status_code in (204, 205, 304) or data is None:
            return b""

        if not isinstance(data, dict):
            wrapper = {"status_code": status_code, object_label: data}
            return json.dumps(wrapper).encode(self.charset)

        if "errors" in data:
            return super().render(data, accepted_media_type, renderer_context)

        wrapped = {"status_code": status_code, object_label: data}

        return json.dumps(wrapped).encode(self.charset)
