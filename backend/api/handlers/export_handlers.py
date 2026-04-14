from rest_framework import status
from rest_framework.response import Response


class BaseExportHandler:
    request_serializer_class = None
    response_serializer_class = None
    validation_error_types = tuple()
    generation_error_types = tuple()
    invalid_request_message = ""
    internal_error_message = ""
    validation_log_message = ""
    generation_log_message = ""
    unexpected_log_message = ""
    invalid_metadata_message = ""

    def __init__(
        self,
        strategy,
        build_error_response,
        build_success_response,
    ):
        self.strategy = strategy
        self.build_error_response = build_error_response
        self.build_success_response = build_success_response

    def handle(self, request):
        serializer = self.request_serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            metadata = self.strategy.export_to_filesystem(
                serializer.validated_data["output_json"]
            )
        except Exception as exc:
            return self.build_error_response(
                error=exc,
                validation_error_types=self.validation_error_types,
                generation_error_types=self.generation_error_types,
                invalid_request_message=self.invalid_request_message,
                internal_error_message=self.internal_error_message,
                validation_log_message=self.validation_log_message,
                generation_log_message=self.generation_log_message,
                unexpected_log_message=self.unexpected_log_message,
            )

        return self.build_success_response(
            metadata=metadata,
            response_serializer_class=self.response_serializer_class,
            invalid_metadata_message=self.invalid_metadata_message,
        )


class CsvExportHandler(BaseExportHandler):
    pass


class ExcelExportHandler(BaseExportHandler):
    pass
