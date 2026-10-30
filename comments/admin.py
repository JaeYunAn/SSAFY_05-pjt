from django.contrib import admin

from .models import CommentAnalysis

admin.site.site_header = "채움 관리자"
admin.site.site_title = "채움 관리자"


@admin.register(CommentAnalysis)
class CommentAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "query", "stock_name", "stock_code", "status", "raw_count", "cleaned_count",
                    "augmented_count", "created_at")
    list_filter = ("status",)
    search_fields = ("query", "stock_name")
    readonly_fields = ("created_at",)

    @admin.display(description="원본")
    def raw_count(self, obj):
        return len(obj.raw_comments)

    @admin.display(description="정제")
    def cleaned_count(self, obj):
        return len(obj.cleaned_comments)

    @admin.display(description="증강")
    def augmented_count(self, obj):
        return len(obj.augmented_comments)
