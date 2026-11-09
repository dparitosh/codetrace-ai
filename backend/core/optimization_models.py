"""Explicit product/deployment context and reproducible optimization assumptions."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal, Annotated

class ProductUnit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_.-]+$')
    entrypoints: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(min_length=1, max_length=32)
    features: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=32)
    kind: Literal['deployment', 'product_variant', 'structural_directory'] = 'deployment'

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_.-]+$')]

class Capability(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Identifier
    label: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=2000)
    owner: str = Field(default='', max_length=200)

class Feature(Capability):
    capability_id: Identifier
    kind: Literal['mandatory', 'optional', 'alternative'] = 'optional'
    alternative_group: str = Field(default='', max_length=100)
    binding_time: Literal['unspecified','build','deploy','runtime'] = 'unspecified'
    requires: list[Identifier] = Field(default_factory=list, max_length=100)
    excludes: list[Identifier] = Field(default_factory=list, max_length=100)
    paths: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(default_factory=list, max_length=100)
    function_ids: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(default_factory=list, max_length=100)
    operation_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=100)

class ProductVariant(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Identifier
    features: list[Identifier] = Field(default_factory=list, max_length=100)

class DocumentEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=4000)
    feature_ids: list[Identifier] = Field(default_factory=list, max_length=100)

class ProductContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    family: str = Field(default='', max_length=200)
    capabilities: list[Capability] = Field(default_factory=list, max_length=100)
    features: list[Feature] = Field(default_factory=list, max_length=100)
    products: list[ProductVariant] = Field(default_factory=list, max_length=32)
    documents: list[DocumentEvidence] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def references(self):
        for values in (self.capabilities,self.features,self.products,self.documents):
            if len({v.id for v in values}) != len(values): raise ValueError('Product context IDs must be unique within each collection')
        caps={v.id for v in self.capabilities}; features={v.id for v in self.features}
        for feature in self.features:
            if feature.capability_id not in caps: raise ValueError('Feature references an unknown capability')
            if not set(feature.requires+feature.excludes)<=features: raise ValueError('Feature constraint references an unknown feature')
            if feature.id in feature.excludes or set(feature.requires)&set(feature.excludes): raise ValueError('Contradictory feature constraints')
            if feature.kind=='alternative' and not feature.alternative_group: raise ValueError('Alternative features need an alternative_group')
        if any(not set(p.features)<=features for p in self.products): raise ValueError('Product references an unknown feature')
        if any(not set(d.feature_ids)<=features for d in self.documents): raise ValueError('Document references an unknown feature')
        return self

class OpenAPIArtifact(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Identifier
    document: dict

    @model_validator(mode='after')
    def bounded_document(self):
        import json
        if len(json.dumps(self.document,ensure_ascii=False).encode())>1000000: raise ValueError('OpenAPI document exceeds 1 MB')
        if not str(self.document.get('openapi','')).startswith('3.') and self.document.get('swagger')!='2.0':
            raise ValueError('Expected OpenAPI 3.x or Swagger 2.0 JSON')
        if not isinstance(self.document.get('paths',{}),dict): raise ValueError('OpenAPI paths must be an object')
        return self

class OptimizationOptions(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    units: list[ProductUnit] = Field(default_factory=list, max_length=32)
    include_tests: bool = False
    minimum_function_lines: int = Field(default=8, ge=3, le=1000)
    adoption_rate: float = Field(default=0.5, ge=0, le=1)
    wrapper_lines: int = Field(default=3, ge=0, le=100)
    cell_similarity: float = Field(default=0.65, gt=0, le=1)
    product_context: ProductContext = Field(default_factory=ProductContext)
    openapi_artifacts: list[OpenAPIArtifact] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def unique_contract_ids(self):
        if len({a.id for a in self.openapi_artifacts})!=len(self.openapi_artifacts):
            raise ValueError('OpenAPI artifact IDs must be unique')
        return self
