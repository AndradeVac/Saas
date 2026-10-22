from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.plans import count_products, plan_for
from app.models.category import Category
from app.models.product import Product
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.schemas.menu_import import ImportProduct, MenuImport, MenuImportResult
from app.schemas.product import OptionGroup, OptionItem
from app.services.audit import record_audit


def _size_options(item: ImportProduct) -> list[dict]:
    """Sizes become one required choice; the product keeps the smallest price and each size adds the difference."""
    if len(item.sizes) < 2:
        return []
    group = OptionGroup(
        name="Tamanho", required=True, min=1, max=1,
        options=[OptionItem(name=size.name, price=max(size.price - item.price, 0)) for size in item.sizes],
    )
    return [group.model_dump(mode="json")]


class MenuImportService:
    def __init__(self, db: Session, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.categories = CategoryRepository(db, tenant_id)

    def _category(self, name: str, sort_order: int) -> Category:
        category = self.categories.get_by_name(name)
        if category is None:
            category = Category(name=name, sort_order=sort_order)
            self.categories.create(category)
        elif not category.active:
            category.active = True
        return category

    def apply(self, data: MenuImport, actor: User) -> MenuImportResult:
        """Creates everything in one transaction. Products past the plan's limit are created hidden, so the owner
        sees the whole menu and picks which ones to show."""
        tenant = self.db.get(Tenant, self.tenant_id)
        limit = plan_for(tenant).max_products
        room = None if limit is None else max(limit - count_products(self.db, self.tenant_id), 0)
        next_category = int(self.db.scalar(select(func.coalesce(func.max(Category.sort_order), -1)).where(Category.tenant_id == self.tenant_id))) + 1

        created = hidden = 0
        for index, group in enumerate(data.categories):
            category = self._category(group.name.strip(), min(next_category + index, 1000))
            for position, item in enumerate(group.products):
                show = room is None or created - hidden < room
                price = min([item.price, *(size.price for size in item.sizes)]) if item.sizes else item.price
                item = item.model_copy(update={"price": price})
                self.db.add(Product(
                    tenant_id=self.tenant_id, category_id=category.id, name=item.name.strip(),
                    description=(item.description or "").strip() or None, price=item.price,
                    sort_order=position, options=_size_options(item), active=show,
                ))
                created += 1
                hidden += 0 if show else 1
        record_audit(self.db, self.tenant_id, actor, "MENU_IMPORTED", "TENANT", self.tenant_id, f"{created} produtos ({hidden} ocultos)")
        self.db.commit()
        return MenuImportResult(created=created, hidden=hidden, categories=len(data.categories))
