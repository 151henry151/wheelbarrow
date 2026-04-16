from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Condition(Enum):
    NEW        = "new"
    GOOD       = "good"
    WEATHERED  = "weathered"
    WORN       = "worn"
    REPAIRED   = "repaired"
    RUSTED     = "rusted"
    BROKEN     = "broken"

    def degrade(self) -> "Condition":
        """Return the next worse condition."""
        order = [
            Condition.NEW,
            Condition.GOOD,
            Condition.WEATHERED,
            Condition.WORN,
            Condition.RUSTED,
            Condition.BROKEN,
        ]
        idx = order.index(self) if self in order else len(order) - 1
        return order[min(idx + 1, len(order) - 1)]


class Material(Enum):
    STEEL  = "steel"
    RUBBER = "rubber"
    MAPLE  = "maple"
    PINE   = "pine"
    PLASTIC = "plastic"
    IRON   = "iron"


# ---------------------------------------------------------------------------
# Cargo
# ---------------------------------------------------------------------------

@dataclass
class Cargo:
    name: str
    weight_lbs: float
    volume_gallons: float

    def __repr__(self) -> str:
        return f"Cargo({self.name!r}, {self.weight_lbs} lbs, {self.volume_gallons} gal)"


# ---------------------------------------------------------------------------
# Component base class
# ---------------------------------------------------------------------------

@dataclass
class Component:
    material: Material
    color: str
    condition: Condition

    def inspect(self) -> str:
        return (
            f"{type(self).__name__}: {self.material.value}, {self.color}, "
            f"condition={self.condition.value}"
        )

    def degrade(self) -> None:
        """Worsen condition by one step."""
        self.condition = self.condition.degrade()

    def repair(self) -> None:
        """Restore condition to GOOD."""
        self.condition = Condition.GOOD

    @property
    def is_functional(self) -> bool:
        return self.condition != Condition.BROKEN


# ---------------------------------------------------------------------------
# Specific components
# ---------------------------------------------------------------------------

@dataclass
class Wheel(Component):
    diameter_inches: float = 16.0
    tire_material: Material = Material.RUBBER
    tire_pressure_psi: float = 31.0
    tire_condition: Condition = Condition.GOOD

    _RECOMMENDED_PSI: float = field(default=30.0, init=False, repr=False)

    def inflate(self, psi: float) -> None:
        if psi <= 0:
            raise ValueError("Pressure must be positive.")
        self.tire_pressure_psi = psi
        print(f"Tire inflated to {self.tire_pressure_psi} psi.")

    def deflate(self, amount_psi: float) -> None:
        self.tire_pressure_psi = max(0.0, self.tire_pressure_psi - amount_psi)
        if self.tire_pressure_psi == 0:
            print("Tire is flat!")
            self.tire_condition = Condition.BROKEN
        else:
            print(f"Tire pressure now {self.tire_pressure_psi} psi.")

    @property
    def is_flat(self) -> bool:
        return self.tire_pressure_psi <= 0

    @property
    def pressure_ok(self) -> bool:
        return self.tire_pressure_psi >= self._RECOMMENDED_PSI * 0.8

    def inspect(self) -> str:
        base = super().inspect()
        tire_status = "flat" if self.is_flat else f"{self.tire_pressure_psi} psi"
        return f"{base} | tire: {tire_status}, {self.tire_condition.value}"


@dataclass
class Bucket(Component):
    capacity_gallons: float = 5.0
    capacity_lbs: float = 300.0
    _cargo: list[Cargo] = field(default_factory=list, init=False, repr=False)

    @property
    def cargo(self) -> list[Cargo]:
        return list(self._cargo)

    @property
    def current_weight_lbs(self) -> float:
        return sum(c.weight_lbs for c in self._cargo)

    @property
    def current_volume_gallons(self) -> float:
        return sum(c.volume_gallons for c in self._cargo)

    @property
    def is_empty(self) -> bool:
        return len(self._cargo) == 0

    @property
    def is_overloaded(self) -> bool:
        return (
            self.current_weight_lbs > self.capacity_lbs
            or self.current_volume_gallons > self.capacity_gallons
        )

    @property
    def weight_remaining_lbs(self) -> float:
        return max(0.0, self.capacity_lbs - self.current_weight_lbs)

    @property
    def volume_remaining_gallons(self) -> float:
        return max(0.0, self.capacity_gallons - self.current_volume_gallons)

    def load(self, cargo: Cargo) -> None:
        if not self.is_functional:
            raise RuntimeError("Bucket is broken and cannot hold cargo.")
        self._cargo.append(cargo)
        if self.is_overloaded:
            print(
                f"Warning: bucket is overloaded! "
                f"{self.current_weight_lbs:.1f} lbs / {self.capacity_lbs} lbs, "
                f"{self.current_volume_gallons:.1f} gal / {self.capacity_gallons} gal"
            )
        else:
            print(
                f"Loaded {cargo.name}. Bucket: "
                f"{self.current_weight_lbs:.1f}/{self.capacity_lbs} lbs, "
                f"{self.current_volume_gallons:.2f}/{self.capacity_gallons} gal"
            )

    def unload(self, cargo_name: Optional[str] = None) -> list[Cargo]:
        """Unload a specific item by name, or everything if no name given."""
        if cargo_name is None:
            dumped = list(self._cargo)
            self._cargo.clear()
            print(f"Bucket emptied. Dumped {len(dumped)} item(s).")
            return dumped
        matches = [c for c in self._cargo if c.name == cargo_name]
        if not matches:
            print(f"No cargo named {cargo_name!r} found.")
            return []
        for item in matches:
            self._cargo.remove(item)
        print(f"Removed {len(matches)}x {cargo_name!r} from bucket.")
        return matches

    def inspect(self) -> str:
        base = super().inspect()
        fill = f"{self.current_weight_lbs:.1f}/{self.capacity_lbs} lbs"
        items = ", ".join(c.name for c in self._cargo) or "empty"
        return f"{base} | {fill} | contents: {items}"


@dataclass
class Handle(Component):
    side: str  # "left" or "right"
    length_inches: float = 48.0
    grip_worn: bool = False

    def inspect(self) -> str:
        base = super().inspect()
        grip = "grip worn" if self.grip_worn else "grip ok"
        return f"{base} | {self.side} handle, {self.length_inches}\" | {grip}"


@dataclass
class SupportFrame(Component):
    """The legs/feet and nose plate that keep the barrow upright when parked."""
    pass


# ---------------------------------------------------------------------------
# Wheelbarrow
# ---------------------------------------------------------------------------

class Wheelbarrow:
    """
    A model of a single-wheel wheelbarrow.

    Attributes
    ----------
    wheel        : front wheel assembly
    bucket       : load-bearing tray
    left_handle  : left operator handle
    right_handle : right operator handle
    frame        : support feet + nose plate
    owner        : optional owner name
    """

    def __init__(
        self,
        wheel: Wheel,
        bucket: Bucket,
        left_handle: Handle,
        right_handle: Handle,
        frame: SupportFrame,
        owner: Optional[str] = None,
    ):
        self.wheel = wheel
        self.bucket = bucket
        self.left_handle = left_handle
        self.right_handle = right_handle
        self.frame = frame
        self.owner = owner
        self._distance_traveled_ft: float = 0.0
        self._trips: int = 0

    # -- Dunder methods --

    def __repr__(self) -> str:
        return (
            f"Wheelbarrow(owner={self.owner!r}, "
            f"load={self.bucket.current_weight_lbs:.1f} lbs, "
            f"trips={self._trips})"
        )

    def __str__(self) -> str:
        lines = [
            "=== Wheelbarrow ===",
            f"  Owner    : {self.owner or 'unknown'}",
            f"  Trips    : {self._trips}",
            f"  Distance : {self._distance_traveled_ft:.1f} ft",
            f"  Load     : {self.bucket.current_weight_lbs:.1f} lbs "
                         f"/ {self.bucket.capacity_lbs} lbs",
            "",
            "  Components:",
            f"    {self.wheel.inspect()}",
            f"    {self.bucket.inspect()}",
            f"    {self.left_handle.inspect()}",
            f"    {self.right_handle.inspect()}",
            f"    {self.frame.inspect()}",
        ]
        return "\n".join(lines)

    def __len__(self) -> int:
        """Number of cargo items currently loaded."""
        return len(self.bucket.cargo)

    # -- Operational properties --

    @property
    def total_weight_lbs(self) -> float:
        """Approximate total weight (cargo + ~50 lb empty barrow)."""
        EMPTY_WEIGHT = 50.0
        return EMPTY_WEIGHT + self.bucket.current_weight_lbs

    @property
    def is_ready(self) -> bool:
        """True if all components are functional and tire pressure is ok."""
        components = [self.wheel, self.bucket, self.left_handle, self.right_handle, self.frame]
        return all(c.is_functional for c in components) and self.wheel.pressure_ok

    @property
    def overall_condition(self) -> Condition:
        """Worst condition among all components."""
        conditions = [
            self.wheel.condition,
            self.wheel.tire_condition,
            self.bucket.condition,
            self.left_handle.condition,
            self.right_handle.condition,
            self.frame.condition,
        ]
        order = list(Condition)
        return max(conditions, key=lambda c: order.index(c))

    # -- Actions --

    def load(self, cargo: Cargo) -> None:
        self.bucket.load(cargo)

    def unload(self, cargo_name: Optional[str] = None) -> list[Cargo]:
        return self.bucket.unload(cargo_name)

    def push(self, distance_ft: float) -> None:
        """Push the wheelbarrow a given distance."""
        if not self.is_ready:
            issues = self._list_issues()
            raise RuntimeError(f"Wheelbarrow is not ready to push. Issues: {issues}")
        if self.bucket.is_overloaded:
            print("Warning: pushing an overloaded wheelbarrow — watch your back!")
        self._distance_traveled_ft += distance_ft
        self._trips += 1
        print(
            f"Pushed {distance_ft} ft "
            f"({'empty' if self.bucket.is_empty else f'{self.bucket.current_weight_lbs:.1f} lbs'})."
        )
        self._apply_wear()

    def tip(self) -> list[Cargo]:
        """Tip the bucket to dump all contents."""
        if self.bucket.is_empty:
            print("Nothing to tip — bucket is already empty.")
            return []
        dumped = self.bucket.unload()
        print(f"Tipped! Dumped {sum(c.weight_lbs for c in dumped):.1f} lbs.")
        return dumped

    def inspect(self) -> str:
        return str(self)

    def service(self) -> None:
        """Full service: repair all components and re-inflate tire."""
        for component in [self.wheel, self.bucket, self.left_handle, self.right_handle, self.frame]:
            component.repair()
        self.wheel.tire_condition = Condition.GOOD
        self.wheel.inflate(30.0)
        self.left_handle.grip_worn = False
        self.right_handle.grip_worn = False
        print("Wheelbarrow fully serviced. All components restored to GOOD condition.")

    # -- Internal helpers --

    def _apply_wear(self) -> None:
        """Degrade components based on accumulated use."""
        interval = 50  # degrade every 50 trips
        if self._trips % interval == 0:
            self.wheel.degrade()
            self.frame.degrade()
            print(f"[wear] {self._trips} trips — wheel and frame show wear.")
        if self._trips % (interval * 2) == 0:
            self.bucket.degrade()
            print(f"[wear] {self._trips} trips — bucket shows wear.")
        if self._trips % 10 == 0:
            self.wheel.deflate(0.5)

    def _list_issues(self) -> list[str]:
        issues = []
        if self.wheel.is_flat:
            issues.append("flat tire")
        if not self.wheel.pressure_ok:
            issues.append(f"low tire pressure ({self.wheel.tire_pressure_psi} psi)")
        for c in [self.wheel, self.bucket, self.left_handle, self.right_handle, self.frame]:
            if not c.is_functional:
                issues.append(f"{type(c).__name__} is broken")
        return issues


# ---------------------------------------------------------------------------
# Factory: build the original weathered wheelbarrow from the old dict model
# ---------------------------------------------------------------------------

def build_my_wheelbarrow(owner: Optional[str] = None) -> Wheelbarrow:
    """Recreate the original wheelbarrow — same parts, now in proper objects."""
    return Wheelbarrow(
        wheel=Wheel(
            material=Material.STEEL,
            color="blue",
            condition=Condition.WEATHERED,
            diameter_inches=16.0,
            tire_material=Material.RUBBER,
            tire_pressure_psi=31.0,
            tire_condition=Condition.GOOD,
        ),
        bucket=Bucket(
            material=Material.STEEL,
            color="blue",
            condition=Condition.RUSTED,
            capacity_gallons=5.0,
            capacity_lbs=300.0,
        ),
        left_handle=Handle(
            material=Material.MAPLE,
            color="natural",
            condition=Condition.WEATHERED,
            side="left",
        ),
        right_handle=Handle(
            material=Material.PINE,
            color="natural",
            condition=Condition.REPAIRED,
            side="right",
        ),
        frame=SupportFrame(
            material=Material.STEEL,
            color="blue",
            condition=Condition.WEATHERED,
        ),
        owner=owner,
    )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    wb = build_my_wheelbarrow(owner="Henry")
    print(wb)
    print()

    # Load it up
    wb.load(Cargo("topsoil",    weight_lbs=80.0,  volume_gallons=2.0))
    wb.load(Cargo("compost",    weight_lbs=40.0,  volume_gallons=1.5))
    wb.load(Cargo("gravel bag", weight_lbs=50.0,  volume_gallons=0.8))
    print()

    # Push it across the yard
    wb.push(distance_ft=60)
    print()

    # Tip the load at the garden bed
    wb.tip()
    print()

    # Quick status
    print(f"Items loaded: {len(wb)}")
    print(f"Total weight: {wb.total_weight_lbs:.1f} lbs")
    print(f"Overall condition: {wb.overall_condition.value}")
    print(f"Ready to work: {wb.is_ready}")
