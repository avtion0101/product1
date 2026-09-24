import math
from collections import defaultdict, deque
from copy import deepcopy


class Engine:
    def __init__(self):
        self.ratio_tolerance = 1e-9
        self.sum_tolerance = 1e-6
        self.max_paths = 10000
        self.max_depth = 200
        self.allowed_types = {
            'product',
            'compound',
            'ingredient',
            'additive',
        }
        self.type_names = {
            'product': '成品',
            'compound': '复合配料',
            'ingredient': '普通配料',
            'additive': '添加剂',
        }

    def example(self):
        return {
            'product_id': 'P001',
            'target_additive': 'A001',
            'batch_id': 'B20260923',
            'formula_version': 'V3.2',
            'nodes': [
                {
                    'id': 'P001',
                    'name': '调味肉制品',
                    'type': 'product',
                },
                {
                    'id': 'C001',
                    'name': '复合腌制料',
                    'type': 'compound',
                },
                {
                    'id': 'C002',
                    'name': '复合保水剂',
                    'type': 'compound',
                },
                {
                    'id': 'I001',
                    'name': '猪肉',
                    'type': 'ingredient',
                },
                {
                    'id': 'I002',
                    'name': '食用盐',
                    'type': 'ingredient',
                },
                {
                    'id': 'I003',
                    'name': '淀粉',
                    'type': 'ingredient',
                },
                {
                    'id': 'A001',
                    'name': '三聚磷酸钠',
                    'type': 'additive',
                },
                {
                    'id': 'A002',
                    'name': '焦磷酸钠',
                    'type': 'additive',
                },
            ],
            'relations': [
                {
                    'parent': 'P001',
                    'child': 'I001',
                    'ratio': 0.80,
                },
                {
                    'parent': 'P001',
                    'child': 'C001',
                    'ratio': 0.15,
                },
                {
                    'parent': 'P001',
                    'child': 'I003',
                    'ratio': 0.05,
                },
                {
                    'parent': 'C001',
                    'child': 'I002',
                    'ratio': 0.60,
                },
                {
                    'parent': 'C001',
                    'child': 'C002',
                    'ratio': 0.40,
                },
                {
                    'parent': 'C002',
                    'child': 'A001',
                    'ratio': 0.70,
                },
                {
                    'parent': 'C002',
                    'child': 'A002',
                    'ratio': 0.30,
                },
            ],
        }

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('输入必须是对象')
        required = (
            'product_id',
            'target_additive',
            'batch_id',
            'formula_version',
            'nodes',
            'relations',
        )
        for field in required:
            if field not in payload:
                raise ValueError('缺少字段：' + field)
        self._validate_text(payload['product_id'], 'product_id')
        self._validate_text(payload['target_additive'], 'target_additive')
        self._validate_text(payload['batch_id'], 'batch_id')
        self._validate_text(payload['formula_version'], 'formula_version')
        nodes = payload['nodes']
        relations = payload['relations']
        if not isinstance(nodes, list):
            raise ValueError('nodes必须是数组')
        if not isinstance(relations, list):
            raise ValueError('relations必须是数组')
        if not nodes:
            raise ValueError('nodes不能为空')
        if len(nodes) > 5000:
            raise ValueError('节点数量不能超过5000')
        if len(relations) > 20000:
            raise ValueError('关系数量不能超过20000')
        node_map = self._validate_nodes(nodes)
        product_id = payload['product_id']
        target_id = payload['target_additive']
        if product_id not in node_map:
            raise ValueError('成品节点不存在')
        if target_id not in node_map:
            raise ValueError('目标添加剂节点不存在')
        if node_map[product_id]['type'] != 'product':
            raise ValueError('product_id必须指向成品节点')
        if node_map[target_id]['type'] != 'additive':
            raise ValueError('target_additive必须指向添加剂节点')
        self._validate_relations(relations, node_map)
        self._validate_product_count(nodes, product_id)
        self._validate_parent_types(relations, node_map)
        self._validate_duplicate_relations(relations)
        self._validate_ratio_totals_upper_bound(relations)
        self._validate_optional_settings(payload)
        return None

    def _validate_text(self, value, field):
        if not isinstance(value, str):
            raise ValueError(field + '必须是字符串')
        if not value.strip():
            raise ValueError(field + '不能为空')
        if value != value.strip():
            raise ValueError(field + '首尾不能含空白')
        if len(value) > 200:
            raise ValueError(field + '长度不能超过200')
        if any(ord(char) < 32 for char in value):
            raise ValueError(field + '不能含控制字符')

    def _validate_nodes(self, nodes):
        node_map = {}
        for index, node in enumerate(nodes):
            label = 'nodes[' + str(index) + ']'
            if not isinstance(node, dict):
                raise ValueError(label + '必须是对象')
            for field in ('id', 'name', 'type'):
                if field not in node:
                    raise ValueError(label + '缺少字段：' + field)
            self._validate_text(node['id'], label + '.id')
            self._validate_text(node['name'], label + '.name')
            self._validate_text(node['type'], label + '.type')
            node_id = node['id']
            node_type = node['type']
            if node_type not in self.allowed_types:
                raise ValueError(label + '.type不是允许的类型')
            if node_id in node_map:
                raise ValueError('节点编号重复：' + node_id)
            node_map[node_id] = node
        return node_map

    def _validate_relations(self, relations, node_map):
        for index, relation in enumerate(relations):
            label = 'relations[' + str(index) + ']'
            if not isinstance(relation, dict):
                raise ValueError(label + '必须是对象')
            if 'parent' not in relation:
                raise ValueError(label + '缺少字段：parent')
            if 'child' not in relation:
                raise ValueError(label + '缺少字段：child')
            self._validate_text(relation['parent'], label + '.parent')
            self._validate_text(relation['child'], label + '.child')
            parent = relation['parent']
            child = relation['child']
            if parent not in node_map:
                raise ValueError(label + '引用了未知父节点')
            if child not in node_map:
                raise ValueError(label + '引用了未知子节点')
            if parent == child:
                raise ValueError(label + '不允许节点直接引用自身')
            if 'ratio' in relation:
                ratio = relation['ratio']
                if ratio is not None:
                    self._validate_ratio(ratio, label + '.ratio')

    def _validate_ratio(self, ratio, label):
        if isinstance(ratio, bool):
            raise ValueError(label + '必须是数字')
        if not isinstance(ratio, (int, float)):
            raise ValueError(label + '必须是数字或null')
        if not math.isfinite(ratio):
            raise ValueError(label + '必须是有限数字')
        if ratio < 0:
            raise ValueError(label + '不能小于0')
        if ratio > 1:
            raise ValueError(label + '不能大于1')

    def _validate_product_count(self, nodes, product_id):
        products = []
        for node in nodes:
            if node['type'] == 'product':
                products.append(node['id'])
        if product_id not in products:
            raise ValueError('指定成品类型不正确')

    def _validate_parent_types(self, relations, node_map):
        allowed = {'product', 'compound'}
        for relation in relations:
            parent = relation['parent']
            if node_map[parent]['type'] not in allowed:
                raise ValueError('普通配料或添加剂不能包含子配料：' + parent)

    def _validate_duplicate_relations(self, relations):
        seen = set()
        for relation in relations:
            key = (relation['parent'], relation['child'])
            if key in seen:
                raise ValueError('配料关系重复：' + key[0] + '->' + key[1])
            seen.add(key)

    def _validate_ratio_totals_upper_bound(self, relations):
        totals = defaultdict(float)
        complete = defaultdict(bool)
        for relation in relations:
            ratio = relation.get('ratio')
            if ratio is None:
                continue
            totals[relation['parent']] += float(ratio)
            complete[relation['parent']] = True
        for parent, total in totals.items():
            if complete[parent] and total > 1 + self.sum_tolerance:
                raise ValueError('同层配比合计超过100%：' + parent)

    def _validate_optional_settings(self, payload):
        if 'sum_tolerance' in payload:
            value = payload['sum_tolerance']
            if isinstance(value, bool):
                raise ValueError('sum_tolerance必须是数字')
            if not isinstance(value, (int, float)):
                raise ValueError('sum_tolerance必须是数字')
            if not math.isfinite(value):
                raise ValueError('sum_tolerance必须是有限数字')
            if value <= 0 or value > 0.01:
                raise ValueError('sum_tolerance必须大于0且不超过0.01')
        if 'max_paths' in payload:
            value = payload['max_paths']
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError('max_paths必须是整数')
            if value < 1 or value > 100000:
                raise ValueError('max_paths范围为1至100000')

    def calculate(self, payload):
        self.validate(payload)
        data = deepcopy(payload)
        node_map = self._make_node_map(data['nodes'])
        adjacency = self._make_adjacency(data['relations'])
        reverse = self._make_reverse_adjacency(data['relations'])
        reachable = self._reachable_from(data['product_id'], adjacency)
        relevant = self._relevant_nodes(
            data['product_id'],
            data['target_additive'],
            adjacency,
            reverse,
        )
        cycles = self._find_cycles(adjacency, reachable)
        relevant_cycles = self._filter_relevant_cycles(cycles, relevant)
        tolerance = data.get('sum_tolerance', self.sum_tolerance)
        layer_status = self._analyze_layers(
            adjacency,
            node_map,
            reachable,
            tolerance,
        )
        missing = self._collect_missing_ratios(data['relations'], reachable)
        incomplete = self._collect_incomplete_layers(layer_status)
        max_paths = data.get('max_paths', self.max_paths)
        paths, truncated = self._enumerate_paths(
            data['product_id'],
            data['target_additive'],
            adjacency,
            max_paths,
        )
        path_rows = self._build_path_rows(
            paths,
            node_map,
            layer_status,
            relevant_cycles,
        )
        summary_data = self._summarize_contributions(path_rows)
        network_rows = self._build_network_rows(
            data['relations'],
            node_map,
            reachable,
            relevant,
            layer_status,
        )
        edges, edge_rows = self._build_edges(
            data['nodes'],
            data['relations'],
            reachable,
        )
        review_items = self._build_review_items(
            paths,
            relevant_cycles,
            missing,
            incomplete,
            truncated,
            summary_data,
        )
        summary = self._build_summary(
            data,
            paths,
            relevant_cycles,
            summary_data,
            truncated,
        )
        metrics = self._build_metrics(
            data,
            reachable,
            paths,
            relevant_cycles,
            missing,
            incomplete,
            summary_data,
            truncated,
        )
        series = self._build_series(
            path_rows,
            paths,
            relevant_cycles,
        )
        result = {
            'summary': summary,
            'metrics': metrics,
            'rows': path_rows,
            'series': series,
            'chart_title': '复合配料中目标添加剂来源路径网络',
            'edges': edges,
            'network_rows': network_rows,
            'edge_rows': edge_rows,
            'cycle_nodes': self._flatten_cycles(relevant_cycles),
            'missing_ratios': missing,
            'incomplete_layers': incomplete,
            'review_items': review_items,
            'batch_id': data['batch_id'],
            'formula_version': data['formula_version'],
            'target_additive': data['target_additive'],
            'path_count': len(paths),
            'truncated': truncated,
            'method': self._method_text(),
            'limitations': self._limitations_text(),
        }
        self._ensure_json_safe(result)
        return result

    def _make_node_map(self, nodes):
        result = {}
        for node in nodes:
            result[node['id']] = node
        return result

    def _make_adjacency(self, relations):
        adjacency = defaultdict(list)
        for index, relation in enumerate(relations):
            item = {
                'parent': relation['parent'],
                'child': relation['child'],
                'ratio': relation.get('ratio'),
                'index': index,
            }
            adjacency[relation['parent']].append(item)
        for parent in adjacency:
            adjacency[parent].sort(
                key=lambda item: (item['child'], item['index'])
            )
        return adjacency

    def _make_reverse_adjacency(self, relations):
        reverse = defaultdict(list)
        for relation in relations:
            reverse[relation['child']].append(relation['parent'])
        for child in reverse:
            reverse[child].sort()
        return reverse

    def _reachable_from(self, start, adjacency):
        visited = set()
        stack = [start]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            children = adjacency.get(node, [])
            for relation in reversed(children):
                child = relation['child']
                if child not in visited:
                    stack.append(child)
        return visited

    def _ancestors_of(self, target, reverse):
        visited = set()
        stack = [target]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for parent in reversed(reverse.get(node, [])):
                if parent not in visited:
                    stack.append(parent)
        return visited

    def _relevant_nodes(self, product, target, adjacency, reverse):
        descendants = self._reachable_from(product, adjacency)
        ancestors = self._ancestors_of(target, reverse)
        return descendants.intersection(ancestors)

    def _find_cycles(self, adjacency, reachable):
        color = {}
        stack = []
        positions = {}
        cycles = []
        cycle_keys = set()
        for start in sorted(reachable):
            if color.get(start, 0) != 0:
                continue
            frames = [(start, 0)]
            color[start] = 1
            positions[start] = len(stack)
            stack.append(start)
            while frames:
                node, child_index = frames[-1]
                children = adjacency.get(node, [])
                if child_index >= len(children):
                    frames.pop()
                    color[node] = 2
                    positions.pop(node, None)
                    if stack and stack[-1] == node:
                        stack.pop()
                    continue
                frames[-1] = (node, child_index + 1)
                child = children[child_index]['child']
                if child not in reachable:
                    continue
                state = color.get(child, 0)
                if state == 0:
                    color[child] = 1
                    positions[child] = len(stack)
                    stack.append(child)
                    frames.append((child, 0))
                    continue
                if state == 1:
                    begin = positions[child]
                    cycle = stack[begin:] + [child]
                    key = self._canonical_cycle(cycle)
                    if key not in cycle_keys:
                        cycle_keys.add(key)
                        cycles.append(cycle)
        cycles.sort(key=lambda cycle: tuple(cycle))
        return cycles

    def _canonical_cycle(self, cycle):
        core = cycle[:-1]
        if not core:
            return tuple()
        rotations = []
        for index in range(len(core)):
            rotated = core[index:] + core[:index]
            rotations.append(tuple(rotated))
        return min(rotations)

    def _filter_relevant_cycles(self, cycles, relevant):
        result = []
        for cycle in cycles:
            core = set(cycle[:-1])
            if core.intersection(relevant):
                result.append(cycle)
        return result

    def _analyze_layers(self, adjacency, node_map, reachable, tolerance):
        status = {}
        for parent in sorted(reachable):
            relations = adjacency.get(parent, [])
            if not relations:
                continue
            missing_children = []
            zero_children = []
            total = 0.0
            for relation in relations:
                ratio = relation['ratio']
                if ratio is None:
                    missing_children.append(relation['child'])
                else:
                    total += float(ratio)
                    if abs(float(ratio)) <= self.ratio_tolerance:
                        zero_children.append(relation['child'])
            complete = not missing_children
            balanced = complete and abs(total - 1.0) <= tolerance
            if missing_children:
                reason = '存在缺失配比'
            elif not balanced:
                reason = '同层配比合计不是100%'
            else:
                reason = '配比完整且合计为100%'
            status[parent] = {
                'parent': parent,
                'parent_name': node_map[parent]['name'],
                'total': total,
                'complete': complete,
                'balanced': balanced,
                'computable': complete and balanced,
                'missing_children': missing_children,
                'zero_children': zero_children,
                'reason': reason,
            }
        return status

    def _collect_missing_ratios(self, relations, reachable):
        result = []
        for index, relation in enumerate(relations):
            if relation['parent'] not in reachable:
                continue
            if relation.get('ratio') is None:
                result.append({
                    '关系序号': index + 1,
                    '父节点': relation['parent'],
                    '子节点': relation['child'],
                    '问题': '质量配比缺失',
                })
        return result

    def _collect_incomplete_layers(self, layer_status):
        result = []
        for parent in sorted(layer_status):
            item = layer_status[parent]
            if item['computable']:
                continue
            result.append({
                '父节点': parent,
                '父节点名称': item['parent_name'],
                '已录入配比合计': self._round_number(item['total']),
                '缺失子节点数': len(item['missing_children']),
                '原因': item['reason'],
            })
        return result

    def _enumerate_paths(self, start, target, adjacency, max_paths):
        paths = []
        truncated = False
        node_stack = [start]
        edge_stack = []
        active = {start}

        def visit(node, depth):
            nonlocal truncated
            if truncated:
                return
            if depth > self.max_depth:
                truncated = True
                return
            if node == target:
                paths.append({
                    'nodes': list(node_stack),
                    'edges': [dict(edge) for edge in edge_stack],
                })
                if len(paths) >= max_paths:
                    truncated = True
                return
            for relation in adjacency.get(node, []):
                child = relation['child']
                if child in active:
                    continue
                active.add(child)
                node_stack.append(child)
                edge_stack.append(relation)
                visit(child, depth + 1)
                edge_stack.pop()
                node_stack.pop()
                active.remove(child)
                if truncated:
                    return

        visit(start, 0)
        return paths, truncated

    def _path_layer_problem(self, path, layer_status):
        problems = []
        for parent in path['nodes'][:-1]:
            status = layer_status.get(parent)
            if status is None:
                problems.append(parent + '无子配料层信息')
                continue
            if not status['computable']:
                problems.append(parent + '：' + status['reason'])
        return problems

    def _path_touches_cycle(self, path, cycles):
        path_nodes = set(path['nodes'])
        for cycle in cycles:
            if path_nodes.intersection(cycle[:-1]):
                return True
        return False

    def _path_contribution(self, path):
        contribution = 1.0
        factors = []
        for relation in path['edges']:
            ratio = relation['ratio']
            if ratio is None:
                return None, factors
            value = float(ratio)
            factors.append(value)
            contribution *= value
        return contribution, factors

    def _format_path(self, nodes, node_map):
        names = []
        for node_id in nodes:
            node = node_map[node_id]
            names.append(node['name'] + '(' + node_id + ')')
        return ' → '.join(names)

    def _format_factors(self, factors):
        if not factors:
            return '无'
        values = []
        for factor in factors:
            values.append(self._format_percent(factor))
        return ' × '.join(values)

    def _build_path_rows(
        self,
        paths,
        node_map,
        layer_status,
        relevant_cycles,
    ):
        rows = []
        for index, path in enumerate(paths):
            problems = self._path_layer_problem(path, layer_status)
            touches_cycle = self._path_touches_cycle(path, relevant_cycles)
            contribution, factors = self._path_contribution(path)
            if touches_cycle:
                computable = False
                reason = '相关来源子图存在循环引用'
            elif problems:
                computable = False
                reason = '；'.join(problems)
            elif contribution is None:
                computable = False
                reason = '路径存在缺失配比'
            else:
                computable = True
                reason = '各层配比完整且同层合计正常'
            if computable:
                contribution_value = self._round_number(contribution)
                contribution_percent = self._format_percent(contribution)
            else:
                contribution_value = '不可计算'
                contribution_percent = '不可计算'
            rows.append({
                '路径序号': index + 1,
                '来源路径': self._format_path(path['nodes'], node_map),
                '节点数': len(path['nodes']),
                '层级数': len(path['edges']),
                '比例连乘式': self._format_factors(factors),
                '理论带入比例': contribution_value,
                '理论带入百分比': contribution_percent,
                '计算状态': '可计算' if computable else '不可计算',
                '判定依据': reason,
            })
        return rows

    def _summarize_contributions(self, rows):
        total = 0.0
        computable_count = 0
        unavailable_count = 0
        for row in rows:
            value = row['理论带入比例']
            if isinstance(value, (int, float)):
                total += float(value)
                computable_count += 1
            else:
                unavailable_count += 1
        fully_computable = bool(rows) and unavailable_count == 0
        if fully_computable:
            total_value = self._round_number(total)
            total_percent = self._format_percent(total)
        else:
            total_value = '不可完整计算'
            total_percent = '不可完整计算'
        return {
            'total': total,
            'total_value': total_value,
            'total_percent': total_percent,
            'computable_count': computable_count,
            'unavailable_count': unavailable_count,
            'fully_computable': fully_computable,
        }

    def _build_network_rows(
        self,
        relations,
        node_map,
        reachable,
        relevant,
        layer_status,
    ):
        rows = []
        for node_id in sorted(reachable):
            node = node_map[node_id]
            status = layer_status.get(node_id)
            if status is None:
                layer_state = '叶节点'
                layer_total = '不适用'
            else:
                layer_state = (
                    '完整' if status['computable'] else '需复核'
                )
                layer_total = self._round_number(status['total'])
            rows.append({
                '节点编号': node_id,
                '节点名称': node['name'],
                '节点类型': self.type_names[node['type']],
                '位于目标来源子图': '是' if node_id in relevant else '否',
                '配比层状态': layer_state,
                '子配料合计': layer_total,
            })
        return rows

    def _build_edges(self, nodes, relations, reachable):
        index_by_id = {}
        for index, node in enumerate(nodes):
            index_by_id[node['id']] = index
        edges = []
        rows = []
        for relation in relations:
            parent = relation['parent']
            child = relation['child']
            if parent not in reachable:
                continue
            edges.append([
                index_by_id[parent],
                index_by_id[child],
            ])
            ratio = relation.get('ratio')
            rows.append({
                '父节点': parent,
                '子节点': child,
                '配比': (
                    self._round_number(ratio)
                    if ratio is not None
                    else '缺失'
                ),
                '配比百分比': (
                    self._format_percent(ratio)
                    if ratio is not None
                    else '缺失'
                ),
            })
        return edges, rows

    def _flatten_cycles(self, cycles):
        nodes = set()
        for cycle in cycles:
            nodes.update(cycle[:-1])
        return sorted(nodes)

    def _build_review_items(
        self,
        paths,
        relevant_cycles,
        missing,
        incomplete,
        truncated,
        summary_data,
    ):
        items = []
        if not paths:
            items.append('核对目标添加剂是否已录入成品可达配料层级')
        if relevant_cycles:
            items.append('修正循环引用后再进行相关路径贡献计算')
        if missing:
            items.append('补录缺失的质量配比并确认计量口径一致')
        if incomplete:
            items.append('复核同层配比是否完整且合计为100%')
        if truncated:
            items.append('路径数量达到上限，需缩小配方范围或提高上限')
        if summary_data['fully_computable']:
            items.append('将理论带入估算与成品实验室检测结果分别记录')
        items.append('确认批次与配方版本对应关系')
        items.append('排查未录入配料、加工生成物及污染等其他来源')
        return items

    def _build_summary(
        self,
        data,
        paths,
        relevant_cycles,
        summary_data,
        truncated,
    ):
        target = data['target_additive']
        prefix = (
            '按配方有向图从成品执行深度优先搜索，'
            '枚举至目标添加剂的可能带入路径。'
        )
        if relevant_cycles:
            return (
                prefix
                + '目标来源子图存在循环引用，已停止相关贡献计算；'
                + '当前识别路径'
                + str(len(paths))
                + '条。结果仅表示配方记录中的可能来源关系。'
            )
        if not paths:
            return (
                prefix
                + '未发现从成品到目标添加剂'
                + target
                + '的可达路径，不能据此排除未录入或非配方来源。'
            )
        if summary_data['fully_computable'] and not truncated:
            return (
                prefix
                + '共识别'
                + str(len(paths))
                + '条路径，各层配比完整，沿路径连乘后汇总的理论带入比例为'
                + summary_data['total_percent']
                + '。该估算不能替代成品实验室检测。'
            )
        suffix = '，且路径结果达到枚举上限' if truncated else ''
        return (
            prefix
            + '共识别'
            + str(len(paths))
            + '条路径，其中'
            + str(summary_data['unavailable_count'])
            + '条因配比或结构问题不可计算贡献'
            + suffix
            + '。不对缺失比例作推定。'
        )

    def _build_metrics(
        self,
        data,
        reachable,
        paths,
        relevant_cycles,
        missing,
        incomplete,
        summary_data,
        truncated,
    ):
        return {
            '批次': data['batch_id'],
            '配方版本': data['formula_version'],
            '成品可达节点数': len(reachable),
            '目标来源路径数': len(paths),
            '可计算路径数': summary_data['computable_count'],
            '不可计算路径数': summary_data['unavailable_count'],
            '循环数量': len(relevant_cycles),
            '循环节点数': len(self._flatten_cycles(relevant_cycles)),
            '缺失配比关系数': len(missing),
            '异常配比层数': len(incomplete),
            '理论带入比例合计': summary_data['total_value'],
            '理论带入百分比合计': summary_data['total_percent'],
            '路径是否截断': '是' if truncated else '否',
        }

    def _build_series(self, rows, paths, relevant_cycles):
        series = []
        for row in rows:
            value = row['理论带入比例']
            if isinstance(value, (int, float)):
                number = float(value)
            else:
                number = 0.0
            series.append({
                'label': '路径' + str(row['路径序号']),
                'value': number,
            })
        if not series:
            series.append({
                'label': '未发现来源路径',
                'value': 0.0,
            })
        if relevant_cycles:
            series.append({
                'label': '结构错误循环数',
                'value': float(len(relevant_cycles)),
            })
        return series

    def _format_percent(self, value):
        number = float(value) * 100.0
        text = format(number, '.10f').rstrip('0').rstrip('.')
        if not text:
            text = '0'
        return text + '%'

    def _round_number(self, value):
        number = float(value)
        rounded = round(number, 12)
        if rounded == 0:
            return 0.0
        return rounded

    def _method_text(self):
        return (
            '以成品为起点构建有向配料图，使用深度优先搜索枚举至目标添加剂的路径，'
            '并使用递归活动栈语义检测循环。仅当路径经过的每一配料层均已录入比例且'
            '同层合计在容差内等于100%时，才将各边质量比例连乘并汇总。'
        )

    def _limitations_text(self):
        return (
            '来源追踪仅反映指定批次和配方版本中已录入的可能带入关系，不能证明实际'
            '检测值全部来自相应配料；无法识别未录入配料、加工生成物或污染来源，'
            '理论比例估算不能替代成品实验室检测。'
        )

    def _ensure_json_safe(self, value):
        if value is None:
            return
        if isinstance(value, bool):
            return
        if isinstance(value, str):
            return
        if isinstance(value, int):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError('计算结果包含非有限数字')
            return
        if isinstance(value, list):
            for item in value:
                self._ensure_json_safe(item)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError('计算结果字典键必须是字符串')
                self._ensure_json_safe(item)
            return
        raise ValueError('计算结果包含不可序列化类型')
