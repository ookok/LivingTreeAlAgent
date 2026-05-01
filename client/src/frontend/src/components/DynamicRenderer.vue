<template>
  <div class="dynamic-renderer">
    <component
      v-for="comp in components"
      :key="comp.props.id"
      :is="getComponent(comp.type)"
      v-bind="comp.props"
      @click="handleComponentClick(comp)"
      @change="handleComponentChange(comp, $event)"
      @submit="handleFormSubmit(comp, $event)"
    />
  </div>
</template>

<script setup>import { computed } from 'vue';
import TextInput from './dynamic/TextInput.vue';
import TextArea from './dynamic/TextArea.vue';
import Select from './dynamic/Select.vue';
import MultiSelect from './dynamic/MultiSelect.vue';
import Checkbox from './dynamic/Checkbox.vue';
import RadioGroup from './dynamic/RadioGroup.vue';
import Slider from './dynamic/Slider.vue';
import DatePicker from './dynamic/DatePicker.vue';
import FileUpload from './dynamic/FileUpload.vue';
import Text from './dynamic/Text.vue';
import Heading from './dynamic/Heading.vue';
import Image from './dynamic/Image.vue';
import Table from './dynamic/Table.vue';
import Chart from './dynamic/Chart.vue';
import Card from './dynamic/Card.vue';
import Button from './dynamic/Button.vue';
import Link from './dynamic/Link.vue';
import Toggle from './dynamic/Toggle.vue';
import Row from './dynamic/Row.vue';
import Column from './dynamic/Column.vue';
import Grid from './dynamic/Grid.vue';
import Tabs from './dynamic/Tabs.vue';
import Map from './dynamic/Map.vue';
import Form from './dynamic/Form.vue';
import Dialog from './dynamic/Dialog.vue';
const props = defineProps({
 schema: {
 type: Object,
 required: true
 }
});
const emit = defineEmits(['componentClick', 'formSubmit', 'valueChange']);
// 组件映射
const componentMap = {
 TextInput,
 TextArea,
 Select,
 MultiSelect,
 Checkbox,
 RadioGroup,
 Slider,
 DatePicker,
 FileUpload,
 Text,
 Heading,
 Image,
 Table,
 Chart,
 Card,
 Button,
 Link,
 Toggle,
 Row,
 Column,
 Grid,
 Tabs,
 Map,
 Form,
 Dialog
};
// 获取组件列表
const components = computed(() => {
 if (!props.schema || !props.schema.components) {
 return [];
 }
 return props.schema.components;
});
// 获取组件类型
function getComponent(type) {
 return componentMap[type] || Text;
}
// 处理组件点击
function handleComponentClick(component) {
 emit('componentClick', {
 componentId: component.props.id,
 componentType: component.type
 });
}
// 处理组件值变化
function handleComponentChange(component, event) {
 emit('valueChange', {
 componentId: component.props.id,
 value: event.target?.value || event
 });
}
// 处理表单提交
function handleFormSubmit(component, event) {
 emit('formSubmit', {
 formId: component.props.id,
 data: event
 });
}
</script>

<style scoped>
.dynamic-renderer {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>