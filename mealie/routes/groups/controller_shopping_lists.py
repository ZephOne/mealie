from collections.abc import Callable
from functools import cached_property

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4

from mealie.routes._base.base_controllers import BaseCrudController
from mealie.routes._base.controller import controller
from mealie.routes._base.mixins import HttpRepo
from mealie.schema.group.group_shopping_list import (
    ShoppingListAddRecipeParams,
    ShoppingListCreate,
    ShoppingListItemCreate,
    ShoppingListItemOut,
    ShoppingListItemsCollectionOut,
    ShoppingListItemUpdate,
    ShoppingListItemUpdateBulk,
    ShoppingListOut,
    ShoppingListPagination,
    ShoppingListRemoveRecipeParams,
    ShoppingListSave,
    ShoppingListSummary,
    ShoppingListUpdate,
)
from mealie.schema.mapper import cast
from mealie.schema.response.pagination import PaginationQuery
from mealie.schema.response.responses import SuccessResponse
from mealie.services.event_bus_service.event_types import (
    EventOperation,
    EventShoppingListData,
    EventShoppingListItemBulkData,
    EventTypes,
)
from mealie.services.group_services.shopping_lists import ShoppingListService

item_router = APIRouter(prefix="/groups/shopping/items", tags=["Group: Shopping List Items"])


def publish_list_item_events(publisher: Callable, items_collection: ShoppingListItemsCollectionOut) -> None:
    items_by_list_id: dict[UUID4, list[ShoppingListItemOut]]
    if items_collection.created_items:
        items_by_list_id = {}
        for item in items_collection.created_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.create,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
            )

    if items_collection.updated_items:
        items_by_list_id = {}
        for item in items_collection.updated_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.update,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
            )

    if items_collection.deleted_items:
        items_by_list_id = {}
        for item in items_collection.deleted_items:
            items_by_list_id.setdefault(item.shopping_list_id, []).append(item)

        for shopping_list_id, items in items_by_list_id.items():
            publisher(
                EventTypes.shopping_list_updated,
                document_data=EventShoppingListItemBulkData(
                    operation=EventOperation.delete,
                    shopping_list_id=shopping_list_id,
                    shopping_list_item_ids=[item.id for item in items],
                ),
            )


@controller(item_router)
class ShoppingListItemController(BaseCrudController):
    @cached_property
    def service(self):
        return ShoppingListService(self.repos)

    @cached_property
    def repo(self):
        return self.repos.group_shopping_list_item

    @cached_property
    def mixins(self):
        return HttpRepo[ShoppingListItemCreate, ShoppingListItemOut, ShoppingListItemCreate](
            self.repo,
            self.logger,
        )

    @item_router.post("/create-bulk", response_model=ShoppingListItemsCollectionOut, status_code=201)
    def create_many(self, data: list[ShoppingListItemCreate]):
        items = self.service.bulk_create_items(data)
        publish_list_item_events(self.publish_event, items)
        return items

    @item_router.post("", response_model=ShoppingListItemsCollectionOut, status_code=201)
    def create_one(self, data: ShoppingListItemCreate):
        return self.create_many([data])

    @item_router.get("/{item_id}", response_model=ShoppingListItemOut)
    def get_one(self, item_id: UUID4):
        return self.mixins.get_one(item_id)

    @item_router.put("", response_model=ShoppingListItemsCollectionOut)
    def update_many(self, data: list[ShoppingListItemUpdateBulk]):
        items = self.service.bulk_update_items(data)
        publish_list_item_events(self.publish_event, items)
        return items

    @item_router.put("/{item_id}", response_model=ShoppingListItemsCollectionOut)
    def update_one(self, item_id: UUID4, data: ShoppingListItemUpdate):
        return self.update_many([data.cast(ShoppingListItemUpdateBulk, id=item_id)])

    @item_router.delete("", response_model=SuccessResponse)
    def delete_many(self, ids: list[UUID4] = Query(None)):
        items = self.service.bulk_delete_items(ids)
        publish_list_item_events(self.publish_event, items)

        message = (
            f"Successfully deleted {len(items.deleted_items)} {'item' if len(items.deleted_items) == 1 else 'items'}"
        )
        return SuccessResponse.respond(message=message)

    @item_router.delete("/{item_id}", response_model=SuccessResponse)
    def delete_one(self, item_id: UUID4):
        return self.delete_many([item_id])


router = APIRouter(prefix="/groups/shopping/lists", tags=["Group: Shopping Lists"])


@controller(router)
class ShoppingListController(BaseCrudController):
    @cached_property
    def service(self):
        return ShoppingListService(self.repos)

    @cached_property
    def repo(self):
        return self.repos.group_shopping_lists.by_group(self.user.group_id)

    # =======================================================================
    # CRUD Operations

    @cached_property
    def mixins(self) -> HttpRepo[ShoppingListCreate, ShoppingListOut, ShoppingListSave]:
        return HttpRepo(self.repo, self.logger, self.registered_exceptions, self.t("generic.server-error"))

    @router.get("", response_model=ShoppingListPagination)
    def get_all(self, q: PaginationQuery = Depends(PaginationQuery)):
        response = self.repo.page_all(
            pagination=q,
            override=ShoppingListSummary,
        )

        response.set_pagination_guides(router.url_path_for("get_all"), q.dict())
        return response

    @router.post("", response_model=ShoppingListOut, status_code=201)
    def create_one(self, data: ShoppingListCreate):
        save_data = cast(data, ShoppingListSave, group_id=self.user.group_id)
        shopping_list = self.mixins.create_one(save_data)

        if shopping_list:
            self.publish_event(
                event_type=EventTypes.shopping_list_created,
                document_data=EventShoppingListData(operation=EventOperation.create, shopping_list_id=shopping_list.id),
                message=self.t("notifications.generic-created", name=shopping_list.name),
            )

        return shopping_list

    @router.get("/{item_id}", response_model=ShoppingListOut)
    def get_one(self, item_id: UUID4):
        return self.mixins.get_one(item_id)

    @router.put("/{item_id}", response_model=ShoppingListOut)
    def update_one(self, item_id: UUID4, data: ShoppingListUpdate):
        shopping_list = self.mixins.update_one(data, item_id)  # type: ignore

        if shopping_list:
            self.publish_event(
                event_type=EventTypes.shopping_list_updated,
                document_data=EventShoppingListData(operation=EventOperation.update, shopping_list_id=shopping_list.id),
                message=self.t("notifications.generic-updated", name=shopping_list.name),
            )

        return shopping_list

    @router.delete("/{item_id}", response_model=ShoppingListOut)
    def delete_one(self, item_id: UUID4):
        shopping_list = self.mixins.delete_one(item_id)  # type: ignore
        if shopping_list:
            self.publish_event(
                event_type=EventTypes.shopping_list_deleted,
                document_data=EventShoppingListData(operation=EventOperation.delete, shopping_list_id=shopping_list.id),
                message=self.t("notifications.generic-deleted", name=shopping_list.name),
            )

        return shopping_list

    # =======================================================================
    # Other Operations

    @router.post("/{item_id}/recipe/{recipe_id}", response_model=ShoppingListOut)
    def add_recipe_ingredients_to_list(
        self, item_id: UUID4, recipe_id: UUID4, data: ShoppingListAddRecipeParams | None = None
    ):
        shopping_list, items = self.service.add_recipe_ingredients_to_list(
            item_id, recipe_id, data.recipe_increment_quantity if data else 1
        )

        publish_list_item_events(self.publish_event, items)
        return shopping_list

    @router.post("/{item_id}/recipe/{recipe_id}/delete", response_model=ShoppingListOut)
    def remove_recipe_ingredients_from_list(
        self, item_id: UUID4, recipe_id: UUID4, data: ShoppingListRemoveRecipeParams | None = None
    ):
        shopping_list, items = self.service.remove_recipe_ingredients_from_list(
            item_id, recipe_id, data.recipe_decrement_quantity if data else 1
        )

        publish_list_item_events(self.publish_event, items)
        return shopping_list
