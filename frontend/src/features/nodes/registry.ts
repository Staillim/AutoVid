import type { NodeTypes } from 'reactflow';
import { SceneNode } from './components/SceneNode';

export const nodeRegistry: NodeTypes = {
  scene: SceneNode,
};
