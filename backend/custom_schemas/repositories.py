from typing import Protocol


class CustomSchemaQueryRepository(Protocol):
    def none(self): ...

    def for_owner(self, owner_id): ...

    def count_for_owner(self, owner_id: object) -> int: ...

    def name_exists_for_owner(
        self,
        owner_id: object,
        name: str,
        exclude_pk: object | None = None,
    ) -> bool: ...


class DjangoCustomSchemaQueryRepository:
    def none(self):
        from .models import CustomSchema

        return CustomSchema.objects.none()

    def for_owner(self, owner_id):
        from .models import CustomSchema

        return CustomSchema.objects.filter(owner_id=owner_id)

    def count_for_owner(self, owner_id: object) -> int:
        return self.for_owner(owner_id).count()

    def name_exists_for_owner(
        self,
        owner_id: object,
        name: str,
        exclude_pk: object | None = None,
    ) -> bool:
        queryset = self.for_owner(owner_id).filter(name=name)
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)
        return queryset.exists()
