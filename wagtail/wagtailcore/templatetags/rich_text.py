import warnings

from wagtail.utils.deprecation import RemovedInWagtail06Warning


warnings.warn(
    "The rich_text tag library has been moved to wagtailcore_tags. "
    "Use {% load wagtailcore_tags %} instead.", RemovedInWagtail06Warning)


from wagtail.wagtailcore.templatetags.wagtailcore_tags import register, richtext
