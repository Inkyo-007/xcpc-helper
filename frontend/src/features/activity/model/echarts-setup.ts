/** ECharts 按需注册：只打包日历热力图与柱状图所需模块。
 * 注意：heatmap 系列必须搭配 visualMap 使用，开发模式下缺失会直接抛
 * "Heatmap must use with visualMap"，VisualMapComponent 不可省略。
 */

import { BarChart, HeatmapChart } from 'echarts/charts'
import {
  CalendarComponent,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  HeatmapChart,
  CalendarComponent,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  SVGRenderer,
])

export { echarts }
export type { EChartsCoreOption } from 'echarts/core'
