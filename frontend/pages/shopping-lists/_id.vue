<template>
  <v-container v-if="shoppingList" class="md-container">
    <BasePageTitle divider>
      <template #header>
        <v-img max-height="100" max-width="100" :src="require('~/static/svgs/shopping-cart.svg')"></v-img>
      </template>
      <template #title> {{ shoppingList.name }} </template>
    </BasePageTitle>

    <!-- Viewer -->
    <section v-if="!edit" class="py-2">
      <div v-if="!byLabel">
        <draggable :value="listItems.unchecked" handle=".handle" @start="loadingCounter += 1" @end="loadingCounter -= 1" @input="updateIndexUnchecked">
          <v-lazy v-for="(item, index) in listItems.unchecked" :key="item.id">
            <ShoppingListItem
              v-model="listItems.unchecked[index]"
              class="my-2 my-sm-0"
              :labels="allLabels || []"
              :units="allUnits || []"
              :foods="allFoods || []"
              @checked="saveListItem"
              @save="saveListItem"
              @delete="deleteListItem(item)"
            />
          </v-lazy>
        </draggable>
      </div>

      <!-- View By Label -->
      <div v-else>
        <div v-for="(value, key) in itemsByLabel" :key="key" class="mb-6">
          <div @click="toggleShowChecked()">
            <span>
              <v-icon>
                {{ $globals.icons.tags }}
              </v-icon>
            </span>
            {{ key }}
          </div>
          <v-lazy v-for="(item, index) in value" :key="item.id">
            <ShoppingListItem
              v-model="value[index]"
              :labels="allLabels || []"
              :units="allUnits || []"
              :foods="allFoods || []"
              @checked="saveListItem"
              @save="saveListItem"
              @delete="deleteListItem(item)"
            />
          </v-lazy>
        </div>
      </div>

      <!-- Create Item -->
      <div v-if="createEditorOpen">
        <ShoppingListItemEditor
          v-model="createListItemData"
          class="my-4"
          :labels="allLabels || []"
          :units="allUnits || []"
          :foods="allFoods || []"
          @delete="createEditorOpen = false"
          @cancel="createEditorOpen = false"
          @save="createListItem"
        />
      </div>
      <div v-else class="mt-4 d-flex justify-end">
        <BaseButton create @click="createEditorOpen = true" />
      </div>

      <!-- Action Bar -->
      <div class="d-flex justify-end mb-4 mt-2">
        <BaseButtonGroup
          :buttons="[
            {
              icon: $globals.icons.contentCopy,
              text: '',
              event: 'edit',
              children: [
                {
                  icon: $globals.icons.contentCopy,
                  text: $tc('shopping-list.copy-as-text'),
                  event: 'copy-plain',
                },
                {
                  icon: $globals.icons.contentCopy,
                  text: $tc('shopping-list.copy-as-markdown'),
                  event: 'copy-markdown',
                },
              ],
            },
            {
              icon: $globals.icons.delete,
              text: $tc('shopping-list.delete-checked'),
              event: 'delete',
            },
            {
              icon: $globals.icons.tags,
              text: $tc('shopping-list.toggle-label-sort'),
              event: 'sort-by-labels',
            },
            {
              icon: $globals.icons.checkboxBlankOutline,
              text: $tc('shopping-list.uncheck-all-items'),
              event: 'uncheck',
            },
          ]"
          @edit="edit = true"
          @delete="deleteChecked"
          @uncheck="uncheckAll"
          @sort-by-labels="sortByLabels"
          @copy-plain="copyListItems('plain')"
          @copy-markdown="copyListItems('markdown')"
        />
      </div>

      <!-- Checked Items -->
      <div v-if="listItems.checked && listItems.checked.length > 0" class="mt-6">
        <button @click="toggleShowChecked()">
          <span>
            <v-icon>
              {{ showChecked ? $globals.icons.chevronDown : $globals.icons.chevronRight }}
            </v-icon>
          </span>
          {{ $tc('shopping-list.items-checked-count', listItems.checked ? listItems.checked.length : 0) }}
        </button>
        <v-divider class="my-4"></v-divider>
        <v-expand-transition>
          <div v-show="showChecked">
            <div v-for="(item, idx) in listItems.checked" :key="item.id">
              <ShoppingListItem
                v-model="listItems.checked[idx]"
                class="strike-through-note"
                :labels="allLabels || []"
                :units="allUnits || []"
                :foods="allFoods || []"
                @checked="saveListItem"
                @save="saveListItem"
                @delete="deleteListItem(item)"
              />
            </div>
          </div>
        </v-expand-transition>
      </div>
    </section>

    <!-- Recipe References -->
    <v-lazy v-if="shoppingList.recipeReferences && shoppingList.recipeReferences.length > 0">
      <section>
        <div>
          <span>
            <v-icon left class="mb-1">
              {{ $globals.icons.primary }}
            </v-icon>
          </span>
          {{ $tc('shopping-list.linked-recipes-count', shoppingList.recipeReferences ? shoppingList.recipeReferences.length : 0) }}
        </div>
        <v-divider class="my-4"></v-divider>
        <RecipeList :recipes="listRecipes">
          <template v-for="(recipe, index) in listRecipes" #[`actions-${recipe.id}`]>
            <v-list-item-action :key="'item-actions-decrease' + recipe.id">
              <v-btn icon @click.prevent="removeRecipeReferenceToList(recipe.id)">
                <v-icon color="grey lighten-1">{{ $globals.icons.minus }}</v-icon>
              </v-btn>
            </v-list-item-action>
            <div :key="'item-actions-quantity' + recipe.id" class="pl-3">
              {{ shoppingList.recipeReferences[index].recipeQuantity }}
            </div>
            <v-list-item-action :key="'item-actions-increase' + recipe.id">
              <v-btn icon @click.prevent="addRecipeReferenceToList(recipe.id)">
                <v-icon color="grey lighten-1">{{ $globals.icons.createAlt }}</v-icon>
              </v-btn>
            </v-list-item-action>
          </template>
        </RecipeList>
      </section>
    </v-lazy>

    <v-lazy>
      <div class="d-flex justify-end mt-10">
        <ButtonLink to="/group/data/labels" :text="$tc('shopping-list.manage-labels')" :icon="$globals.icons.tags" />
      </div>
    </v-lazy>
  </v-container>
</template>

<script lang="ts">
import draggable from "vuedraggable";

import { defineComponent, useAsync, useRoute, computed, ref, watch, onUnmounted, useContext } from "@nuxtjs/composition-api";
import { useIdle, useToggle } from "@vueuse/core";
import { useCopyList } from "~/composables/use-copy";
import { useUserApi } from "~/composables/api";
import { useAsyncKey } from "~/composables/use-utils";
import ShoppingListItem from "~/components/Domain/ShoppingList/ShoppingListItem.vue";
import { ShoppingListItemCreate, ShoppingListItemOut } from "~/lib/api/types/group";
import RecipeList from "~/components/Domain/Recipe/RecipeList.vue";
import ShoppingListItemEditor from "~/components/Domain/ShoppingList/ShoppingListItemEditor.vue";
import { useFoodStore, useLabelStore, useUnitStore } from "~/composables/store";

type CopyTypes = "plain" | "markdown";

interface PresentLabel {
  id: string;
  name: string;
}

export default defineComponent({
  components: {
    draggable,
    ShoppingListItem,
    RecipeList,
    ShoppingListItemEditor,
  },
  setup() {
    const { idle } = useIdle(5 * 60 * 1000) // 5 minutes
    const loadingCounter = ref(1);
    const recipeReferenceLoading = ref(false);
    const userApi = useUserApi();

    const edit = ref(false);
    const byLabel = ref(false);

    const route = useRoute();
    const id = route.value.params.id;

    const { i18n } = useContext();

    // ===============================================================
    // Shopping List Actions

    const shoppingList = useAsync(async () => {
      return await fetchShoppingList();
    }, useAsyncKey());

    async function fetchShoppingList() {
      const { data } = await userApi.shopping.lists.getOne(id);
      return data;
    }

    async function refresh() {
      loadingCounter.value += 1;
      const newListValue = await fetchShoppingList();
      loadingCounter.value -= 1;

      // only update the list with the new value if we're not loading, to prevent UI jitter
      if (!loadingCounter.value) {
        shoppingList.value = newListValue;
      }
    }

    // constantly polls for changes
    async function pollForChanges() {
      // pause polling if the user isn't active or we're busy
      if (idle.value || loadingCounter.value) {
        return;
      }

      try {
        await refresh();

        if (shoppingList.value) {
          attempts = 0;
          return;
        }

        // if the refresh was unsuccessful, the shopping list will be null, so we increment the attempt counter
        attempts ++;
      }

      catch (error) {
        attempts ++;
      }

      // if we hit too many errors, stop polling
      if (attempts >= maxAttempts) {
        clearInterval(pollTimer);
      }
    }

    // start polling
    loadingCounter.value -= 1;
    const pollFrequency = 5000;

    let attempts = 0;
    const maxAttempts = 3;

    const pollTimer: ReturnType<typeof setInterval> = setInterval(() => { pollForChanges() }, pollFrequency);
    onUnmounted(() => {
      clearInterval(pollTimer);
    });

    // =====================================
    // List Item CRUD

    const listItems = computed(() => {
      return {
        checked: shoppingList.value?.listItems?.filter((item) => item.checked) ?? [],
        unchecked: shoppingList.value?.listItems?.filter((item) => !item.checked) ?? [],
      };
    });

    const [showChecked, toggleShowChecked] = useToggle(false);

    // =====================================
    // Copy List Items

    const copy = useCopyList();

    function copyListItems(copyType: CopyTypes) {
      const items = shoppingList.value?.listItems?.filter((item) => !item.checked);

      if (!items) {
        return;
      }

      const text: string[] = items.map((itm) => itm.display || "");

      switch (copyType) {
        case "markdown":
          copy.copyMarkdownCheckList(text);
          break;
        default:
          copy.copyPlain(text);
          break;
      }
    }

    // =====================================
    // Check / Uncheck All

    function uncheckAll() {
      let hasChanged = false;
      shoppingList.value?.listItems?.forEach((item) => {
        if (item.checked) {
          hasChanged = true;
          item.checked = false;
        }
      });
      if (hasChanged) {
        updateListItems();
      }
    }

    function deleteChecked() {
      const checked = shoppingList.value?.listItems?.filter((item) => item.checked);

      if (!checked || checked?.length === 0) {
        return;
      }

      loadingCounter.value += 1;
      deleteListItems(checked);

      loadingCounter.value -= 1;
      refresh();
    }

    // =====================================
    // List Item Context Menu

    const contextActions = {
      delete: "delete",
      setIngredient: "setIngredient",
    };

    const contextMenu = [
      { title: "Delete", action: contextActions.delete },
      { title: "Ingredient", action: contextActions.setIngredient },
    ];

    function contextMenuAction(action: string, item: ShoppingListItemOut, idx: number) {
      if (!shoppingList.value?.listItems) {
        return;
      }

      switch (action) {
        case contextActions.delete:
          shoppingList.value.listItems = shoppingList.value?.listItems.filter((itm) => itm.id !== item.id);
          break;
        case contextActions.setIngredient:
          shoppingList.value.listItems[idx].isFood = !shoppingList.value.listItems[idx].isFood;
          break;
        default:
          break;
      }
    }

    // =====================================
    // Labels, Units, Foods
    // TODO: Extract to Composable

    const { labels: allLabels } = useLabelStore();
    const { units: allUnits } = useUnitStore();
    const { foods: allFoods } = useFoodStore();

    function sortByLabels() {
      byLabel.value = !byLabel.value;
    }

    const presentLabels = computed(() => {
      const labels: PresentLabel[] = [];

      shoppingList.value?.listItems?.forEach((item) => {
        if (item.labelId && item.label) {
          labels.push({
            name: item.label.name,
            id: item.labelId,
          });
        }
      });

      return labels;
    });

    const itemsByLabel = ref<{ [key: string]: ShoppingListItemOut[] }>({});

    function updateItemsByLabel() {
      const items: { [prop: string]: ShoppingListItemOut[] } = {};

      const noLabelText = i18n.tc("shopping-list.no-label");

      const noLabel = [] as ShoppingListItemOut[];

      shoppingList.value?.listItems?.forEach((item) => {
        if (item.checked) {
          return;
        }

        if (item.labelId) {
          if (item.label && item.label.name in items) {
            items[item.label.name].push(item);
          } else if (item.label) {
            items[item.label.name] = [item];
          }
        } else {
          noLabel.push(item);
        }
      });

      if (noLabel.length > 0) {
        items[noLabelText] = noLabel;
      }

      itemsByLabel.value = items;
    }

    watch(shoppingList, () => {
      updateItemsByLabel();
    });

    async function refreshLabels() {
      const { data } = await userApi.multiPurposeLabels.getAll();

      if (data) {
        allLabels.value = data.items ?? [];
      }
    }

    refreshLabels();

    // =====================================
    // Add/Remove Recipe References

    const listRecipes = computed<Array<any>>(() => {
      return shoppingList.value?.recipeReferences?.map((ref) => ref.recipe) ?? [];
    });

    async function addRecipeReferenceToList(recipeId: string) {
      if (!shoppingList.value || recipeReferenceLoading.value) {
        return;
      }

      loadingCounter.value += 1;
      recipeReferenceLoading.value = true;
      const { data } = await userApi.shopping.lists.addRecipe(shoppingList.value.id, recipeId);
      recipeReferenceLoading.value = false;
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    async function removeRecipeReferenceToList(recipeId: string) {
      if (!shoppingList.value || recipeReferenceLoading.value) {
        return;
      }

      loadingCounter.value += 1;
      recipeReferenceLoading.value = true;
      const { data } = await userApi.shopping.lists.removeRecipe(shoppingList.value.id, recipeId);
      recipeReferenceLoading.value = false;
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    // =====================================
    // List Item CRUD

    /*
     * saveListItem updates and update on the backend server. Additionally, if the item is
     * checked it will also append that item to the end of the list so that the unchecked items
     * are at the top of the list.
     */
    async function saveListItem(item: ShoppingListItemOut) {
      if (!shoppingList.value) {
        return;
      }

      loadingCounter.value += 1;
      if (item.checked && shoppingList.value.listItems) {
        const lst = shoppingList.value.listItems.filter((itm) => itm.id !== item.id);
        lst.push(item);
        updateListItems();
      }

      const { data } = await userApi.shopping.items.updateOne(item.id, item);
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    async function deleteListItem(item: ShoppingListItemOut) {
      if (!shoppingList.value) {
        return;
      }

      loadingCounter.value += 1;
      const { data } = await userApi.shopping.items.deleteOne(item.id);
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    // =====================================
    // Create New Item

    const createEditorOpen = ref(false);
    const createListItemData = ref<ShoppingListItemCreate>(ingredientResetFactory());

    function ingredientResetFactory(): ShoppingListItemCreate {
      return {
        shoppingListId: id,
        checked: false,
        position: shoppingList.value?.listItems?.length || 1,
        isFood: false,
        quantity: 1,
        note: "",
        labelId: undefined,
        unitId: undefined,
        foodId: undefined,
      };
    }

    async function createListItem() {
      if (!shoppingList.value) {
        return;
      }

      loadingCounter.value += 1;

      // make sure it's inserted into the end of the list, which may have been updated
      createListItemData.value.position = shoppingList.value?.listItems?.length || 1;
      const { data } = await userApi.shopping.items.createOne(createListItemData.value);
      loadingCounter.value -= 1;

      if (data) {
        createListItemData.value = ingredientResetFactory();
        createEditorOpen.value = false;
        refresh();
      }
    }

    function updateIndexUnchecked(uncheckedItems: ShoppingListItemOut[]) {
      if (shoppingList.value?.listItems) {
        // move the new unchecked items in front of the checked items
        shoppingList.value.listItems = uncheckedItems.concat(listItems.value.checked);
      }

      updateListItems();
    }

    async function deleteListItems(items: ShoppingListItemOut[]) {
      if (!shoppingList.value) {
        return;
      }

      loadingCounter.value += 1;
      const { data } = await userApi.shopping.items.deleteMany(items);
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    async function updateListItems() {
      if (!shoppingList.value?.listItems) {
        return;
      }

      // Set Position
      shoppingList.value.listItems = shoppingList.value.listItems.map((itm: ShoppingListItemOut, idx: number) => {
        itm.position = idx;
        return itm;
      });

      loadingCounter.value += 1;
      const { data } = await userApi.shopping.items.updateMany(shoppingList.value.listItems);
      loadingCounter.value -= 1;

      if (data) {
        refresh();
      }
    }

    return {
      addRecipeReferenceToList,
      updateListItems,
      allLabels,
      byLabel,
      contextMenu,
      contextMenuAction,
      copyListItems,
      createEditorOpen,
      createListItem,
      createListItemData,
      deleteChecked,
      deleteListItem,
      edit,
      itemsByLabel,
      listItems,
      listRecipes,
      loadingCounter,
      presentLabels,
      removeRecipeReferenceToList,
      saveListItem,
      shoppingList,
      showChecked,
      sortByLabels,
      toggleShowChecked,
      uncheckAll,
      updateIndexUnchecked,
      allUnits,
      allFoods,
    };
  },
  head() {
    return {
      title: this.$t("shopping-list.shopping-list") as string,
    };
  },
});
</script>

<style scoped>
.number-input-container {
  max-width: 50px;
}
</style>
