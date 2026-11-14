# CoStar download: schema and coverage (Owner 2)

Names, types and counts only. No rows, contacts or addresses. Source: the kit in `cache/costar/` (private, git-ignored). Scope for this project: Los Angeles (`primaryAddress.researchMarketId = 20`); the kit also holds Houston.

## Datasets

| Dataset (`data/<name>.jsonl`) | Rows | Los Angeles rows | Key | Los Angeles scope |
| --- | ---: | ---: | --- | --- |
| commercial-property | 3,339 | 1,581 | id (PropertyId) | primaryAddress.researchMarketId = 20 |
| commercial-listing-summary | 1,022 | 568 | id; propertyId to commercial-property.id | propertyId joins to a Los Angeles property |
| location-occupancy | 74,093 | 31,258 | id; propertyId to commercial-property.id; tenantLocationId to company-detail.id | propertyId joins to a Los Angeles property |
| company-detail | 49,575 | 20,588 | id (= tenantLocationId) | tenant of an occupancy at a Los Angeles property |
| commercial-sale-comp | 6,120 | 2,767 | id; entities[].propertyId to commercial-property.id | sale includes a Los Angeles property |
| apartment-listing | 1,747 | 767 | id; propertyId to commercial-property.id | propertyId joins to a Los Angeles property |
| residential-listings | 2,120 | 420 | id (MLS listing id) | property.address.city = Los Angeles (all 420 California rows; the rest are Texas) |
| residential-listing-features | 1,899 | 280 | id = residential-listings.id | id joins to a Los Angeles listing |

Starter file `commercial-properties.csv`: columns PropertyId, MatterportModelId, Address, City, State; 13,147 rows for 3,339 properties; one row per property and scan.
Starter file `residential-listings.csv`: columns ListingId, ResidentialListingId, MatterportModelId, Address, City, State; 2,224 rows.

## Top-level columns and types

**commercial-property** (52 columns): `id` BIGINT, `addresses` LIST, `primaryAddress` STRUCT, `propertyType` BIGINT, `propertySubtype` BIGINT, `isCondo` BOOLEAN, `buildingClass` BIGINT, `buildingRating` BIGINT, `buildingRatingType` BIGINT, `constructionStatus` BIGINT, `coStarBuildingType` BIGINT, `buildingName` VARCHAR, `grossBuildingAreaSquareFeet` DOUBLE, `grossTypicalFloorSquareFeet` DOUBLE, `rentableBuildingAreaSquareFeet` DOUBLE, `numStoriesAboveGrade` BIGINT, `constructionEvents` LIST, `buildingConstructionMaterial` BIGINT, `sprinklerType` BIGINT, `hasSprinklers` BOOLEAN, `lotSize` DOUBLE, `lotSizeMeasurementType` BIGINT, `zoningDescription` VARCHAR, `parcelNumbers` LIST, `parcelReferences` LIST, `parking` LIST, `parkingRatio` DOUBLE, `primarySubmarketId` BIGINT, `primaryPhoto` STRUCT, `attachments` LIST, `amenities` LIST, `renovations` LIST, `aliases` LIST, `propertyFlex` STRUCT, `propertyGroupSubtype` BIGINT, `notes` LIST, `contacts` LIST, `environmental` STRUCT, `floors` LIST, `propertyWebsiteUrl` VARCHAR, `propertyOffice` STRUCT, `propertyApartment` STRUCT, `propertyGroupId` BIGINT, `buildingPark` VARCHAR, `buildingHeightInFeet` DOUBLE, `lotLengthInFeet` DOUBLE, `lotWidthInFeet` DOUBLE, `zoningLongDescription` VARCHAR, `propertyIndustrial` STRUCT, `propertyRetail` STRUCT, `propertyHospitality` STRUCT, `land` STRUCT

**commercial-listing-summary** (33 columns): `id` BIGINT, `listingType` BIGINT, `listingStatus` BIGINT, `createdDate` TIMESTAMPTZ, `brokerageCompanyName` VARCHAR, `certifiedFreshDate` TIMESTAMPTZ, `commissionValue` DOUBLE, `transactionValue` DOUBLE, `propertyId` BIGINT, `propertyGroupId` BIGINT, `propertyType` BIGINT, `buildingName` VARCHAR, `buildingSizeSquareFeet` DOUBLE, `buildingClass` BIGINT, `buildingConditionRating` BIGINT, `buildingRating` BIGINT, `constructionCompleteYear` BIGINT, `renovationCompleteYear` BIGINT, `coStarBuildingType` BIGINT, `primarySubmarketId` BIGINT, `address` STRUCT, `notes` LIST, `attachments` LIST, `listingContacts` LIST, `forLeaseSummary` STRUCT, `propertyContacts` LIST, `monetaryUnit` BIGINT, `listingStatusUpdatedDate` TIMESTAMPTZ, `buildingPark` VARCHAR, `listingExpirationInMonths` HUGEINT, `commissionSplitPercent` DOUBLE, `forSaleSummary` STRUCT, `auctionForSaleSummary` STRUCT

**location-occupancy** (12 columns): `addressId` BIGINT, `expirationReason` BIGINT, `fromDate` TIMESTAMPTZ, `id` BIGINT, `industryType` BIGINT, `leaseDeal` STRUCT, `leaseType` BIGINT, `moveInDate` TIMESTAMPTZ, `propertyId` BIGINT, `spaces` LIST, `tenantLocationId` BIGINT, `toDate` TIMESTAMPTZ

**company-detail** (15 columns): `id` BIGINT, `address` STRUCT, `aliases` LIST, `businessStatus` BIGINT, `locationPhone` VARCHAR, `locationPhoneCountryCode` VARCHAR, `numEmployees` BIGINT, `name` VARCHAR, `officeType` BIGINT, `suite` VARCHAR, `brandProfiles` LIST, `profile` STRUCT, `mailingAddress` STRUCT, `latitude` DOUBLE, `longitude` DOUBLE

**commercial-sale-comp** (44 columns): `buildingParkType` BIGINT, `contacts` LIST, `dateOffMarket` TIMESTAMPTZ, `downPayment` BIGINT, `entities` LIST, `escrowLengthInDays` BIGINT, `id` BIGINT, `isLandValueSale` BOOLEAN, `isNoBuyerBroker` BOOLEAN, `isNoListingBroker` BOOLEAN, `monetaryUnit` BIGINT, `notes` LIST, `numberOfEntities` BIGINT, `portfolioType` BIGINT, `proposedLandUse` BIGINT, `saleFinancingType` BIGINT, `salePriceStatus` BIGINT, `saleType` BIGINT, `soldDate` TIMESTAMPTZ, `soldForPrice` BIGINT, `source` BIGINT, `tenure` BIGINT, `transferDocuments` LIST, `pricePerUnit` BIGINT, `capitalizationRateActual` DOUBLE, `grossIncomeMultiplier` DOUBLE, `saleConditions` LIST, `apartments` LIST, `portfolioName` VARCHAR, `capitalizationRateProForma` DOUBLE, `saleMethod` BIGINT, `dateOnMarket` TIMESTAMPTZ, `grossRentMultiplier` DOUBLE, `assessment` STRUCT, `belowMarketSaleReasons` LIST, `pricePerRoom` BIGINT, `forSaleIds` LIST, `verificationSources` LIST, `partialInterestSalePercent` DOUBLE, `askingPriceHigh` BIGINT, `askingPriceLow` BIGINT, `verificationFields` LIST, `marketAssessment` STRUCT, `auctionForSaleIds` LIST

**apartment-listing** (20 columns): `id` BIGINT, `propertyId` BIGINT, `totalNumUnits` BIGINT, `buildingName` VARCHAR, `address` STRUCT, `propertyManagementCompanyId` BIGINT, `propertyManagementCompanyName` VARCHAR, `propertyManagementCompanyHqLocationId` BIGINT, `primaryPhoto` STRUCT, `apartmentModels` LIST, `lifestyleType` BIGINT, `yearBuilt` BIGINT, `primarySubmarketId` BIGINT, `minRent` BIGINT, `maxRent` BIGINT, `monetaryUnit` BIGINT, `numUnitsAvailable` BIGINT, `minSquareFeet` BIGINT, `maxSquareFeet` BIGINT, `totalActiveUnits` BIGINT

**residential-listings** (49 columns): `id` BIGINT, `residentialListingId` BIGINT, `propertyId` BIGINT, `transactionType` BIGINT, `listingStatus` BIGINT, `forSaleStatus` BIGINT, `listDate` TIMESTAMPTZ, `offMarketDate` TIMESTAMPTZ, `contractDate` TIMESTAMPTZ, `currentPrice` DOUBLE, `listingType` BIGINT, `dom` BIGINT, `domDate` TIMESTAMPTZ, `virtualDateOnMarket` TIMESTAMPTZ, `monetaryUnit` BIGINT, `originalPrice` DOUBLE, `remarks` VARCHAR, `sourceNumber` VARCHAR, `specialFeatures` BIGINT, `resoValues` STRUCT, `property` STRUCT, `media` LIST, `agents` LIST, `openHouses` LIST, `permissionLevels` STRUCT, `offices` LIST, `source` STRUCT, `history` LIST, `isPrimaryForThisListingInstance` BOOLEAN, `has3DTour` BOOLEAN, `hasOtherRecentlySoldOrOffMarketListings` BOOLEAN, `hasVideo` BOOLEAN, `costarFeatureValues` STRUCT, `isInCondoBuilding` BOOLEAN, `mls` STRUCT, `closeDate` TIMESTAMPTZ, `closePrice` DOUBLE, `altSourceNumber` VARCHAR, `displayPrice` STRUCT, `attributionContact` VARCHAR, `forRentStatus` BIGINT, `availabilityDate` TIMESTAMPTZ, `rentMax` BIGINT, `rentMin` BIGINT, `certifiedDate` TIMESTAMPTZ, `listPriceMax` BIGINT, `listPriceMin` BIGINT, `newHomesInfo` STRUCT, `removedDate` TIMESTAMPTZ

**residential-listing-features** (5 columns): `id` BIGINT, `highlights` LIST, `sections` LIST, `features` LIST, `derivedValues` STRUCT

Enums are stored as integers; decode with `cache/costar/schemas/enums.json`. STRUCT and LIST columns are nested; see `cache/costar/models/<dataset>.md`.

## Where each Typecast field comes from

| Property field | Source column | Nulls among the 1,581 Los Angeles properties |
| --- | --- | --- |
| property_id | commercial-property `id` | 0 |
| address, city | `primaryAddress` street parts, `.city`, `.state`, `.postcode` | 0 (3 properties spell the city `LOS ANGELES`; normalised) |
| lat, lon | `primaryAddress.latitude`, `primaryAddress.longitude` | 0 |
| type | `propertyType` (integer enum PropertyType) | 0 |
| year_built | `constructionEvents[]` entry with `eventType = 2` (ConstructionComplete); renovation years are never used | 6 |
| size_sqft | `rentableBuildingAreaSquareFeet`, else `grossBuildingAreaSquareFeet` | 3 after the fallback (RBA alone is null for 1,402, mostly multifamily) |
| available | an Active (`listingStatus = 1`) row in commercial-listing-summary for the property | never null |
| contact | `listingContacts[0]` (firstName, lastName, locationName) of the lowest-id active listing | null for 0 of the 269 available properties and for every unlisted property |
| model_id | `commercial-properties.csv` `MatterportModelId` for the same PropertyId (lowest id when several) | 27 (no scan) |

Property-level `contacts[]` in commercial-property carry ids and roles but no names or emails, so they are not used. Listing contacts have names, emails and phones; emails and phones are fake in this kit. `permissionLevels` is not treated as a privacy filter.

## Vacancy and availability

- There is no vacancy flag on a commercial property. "Available" means an Active listing exists (`listingStatus = 1`). The only other status in the kit is 3 (OffMarket, 281 rows).
- Los Angeles active listings: 380 (lease 313, sale 56, auction 11). 46 Los Angeles properties are available only through a sale or auction listing and have no active lease listing, so they are not confirmed vacant space. A listing means space is marketed, not that it is empty.
- Multifamily also has `propertyApartment.vacancyPercent` (647 of 1,417 Los Angeles multifamily properties) and apartment-listing `numUnitsAvailable`; neither feeds `available`.

## Join to Matterport and Vexcel

- Matterport: shared id. `commercial-properties.csv` maps PropertyId to MatterportModelId (the same ids appear as `videoKey` on Matterport attachments, `videoExternalReferenceType` 36 or 234). The property record itself holds no model id.
- Vexcel: no shared id. Vexcel is queried by `lat`/`lon`, which are CoStar's; a Vexcel result is an imagery inference about that point, not a verified match to the CoStar building.
- Result: 1,581 Los Angeles properties; 1,554 have a scan; 269 are available; 260 are both. 1,270 properties have more than one scan, so `cache/property_models.parquet` lists every pair and `Property.model_id` is only the lowest id.
- Matterport check: the hackathon keys list 14,945 models; 5,919 of the 5,920 distinct Los Angeles model ids in the kit are in that list, and every `model_id` in `cache/join.parquet` is in it.

| Property type | Properties | With a scan | Available | Available with a scan |
| --- | ---: | ---: | ---: | ---: |
| Multifamily | 1,417 | 1,402 | 155 | 154 |
| Office | 98 | 90 | 81 | 75 |
| GeneralRetail | 24 | 23 | 15 | 15 |
| Industrial | 24 | 24 | 10 | 10 |
| Flex | 10 | 9 | 4 | 3 |
| Specialty | 3 | 3 | 1 | 1 |
| Land | 3 | 1 | 2 | 1 |
| Hospitality | 1 | 1 | 1 | 1 |
| Healthcare | 1 | 1 | 0 | 0 |

## Open questions, answered

- What links a property to a Matterport model? `MatterportModelId` in `commercial-properties.csv`. To Vexcel? Nothing; coordinates only.
- Which column says a space is vacant or listed? `commercial-listing-summary.listingStatus = 1`. No vacancy flag exists for commercial properties.
- Property type, year built, size, coordinates: see the table above.
- Is there an owner or broker contact? Broker only: `commercial-listing-summary.listingContacts[]` and `brokerageCompanyName`, present for 269 of 269 available properties. Owner contacts carry no names. Otherwise address the note to "listing contact".
- How many Los Angeles properties have a scan, by type? 1,554 in total; by type in the table above.
