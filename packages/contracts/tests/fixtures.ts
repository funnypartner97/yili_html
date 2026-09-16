import sourceFixtures from './fixtures.json';
import registry from '../registries/core-presentation-layouts.json';
export const presentationGraphFixture = sourceFixtures.DocumentGraph;
export const generationPlanFixture = sourceFixtures.GenerationPlan;
export const fixtures = {
  ...sourceFixtures,
  PresentationDocument: sourceFixtures.DocumentGraph.presentation,
  MediaIntent: sourceFixtures.DocumentGraph.assets[0].mediaIntent,
  LayoutRegistry: registry,
};
